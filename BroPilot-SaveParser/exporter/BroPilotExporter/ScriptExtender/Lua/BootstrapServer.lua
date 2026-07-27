--- Exportador de snapshot da party do BroPilot.
--- Grava identidade, stats de build, equipamento por slot e inventário de cada
--- personagem jogável em bropilot_inventory.json, consumido pelo lado Python.

local EXPORT_FILE = "bropilot_inventory.json"
local PROBE_FILE = "bropilot_probe.json"
local SCHEMA_VERSION = 3

--- Intervalo entre tentativas de export, contado em ticks (~60 por segundo).
local EXPORT_INTERVAL_TICKS = 300

--- Slots consultados via Osi.GetEquippedItem. Slot inexistente apenas devolve
--- nil, então a lista pode ser ampla sem custo de correção.
local EQUIPMENT_SLOTS = {
    "Helmet", "Breast", "Cloak", "Gloves", "Boots", "Underwear",
    "Amulet", "Ring", "Ring2",
    "MeleeMainHand", "MeleeOffHand", "RangedMainHand", "RangedOffHand",
    "MainHand", "OffHand",
    "MusicalInstrument", "LightSource",
    "Wings", "Horns", "Overhead",
    "VanityBody", "VanityBoots",
}

--- Ordem dos atributos no array de Abilities do engine.
local ABILITY_NAMES = {
    "Strength", "Dexterity", "Constitution",
    "Intelligence", "Wisdom", "Charisma",
}

--- Executa fn protegido. Devolve nil quando a API não existe ou lança erro.
local function safe(fn)
    local ok, result = pcall(fn)
    if ok then
        return result
    end
    return nil
end

--- Devolve o primeiro candidato que resolver para um valor não nulo.
--- Usado onde o nome do componente ou campo varia entre versões do Script Extender.
local function firstOf(candidates)
    for _, candidate in ipairs(candidates) do
        local value = safe(candidate)
        if value ~= nil then
            return value
        end
    end
    return nil
end

--- Conta as chaves de uma tabela, incluindo mapas não sequenciais.
local function countKeys(t)
    if type(t) ~= "table" then
        return 0
    end
    local n = 0
    for _ in pairs(t) do
        n = n + 1
    end
    return n
end

-- ---------------------------------------------------------------------------
-- Itens e equipamento
-- ---------------------------------------------------------------------------

--- Monta o snapshot de um item a partir da sua entidade.
local function ReadItem(itemEntity)
    if not itemEntity or not itemEntity.Uuid then
        return nil
    end

    local item = {
        UUID = itemEntity.Uuid.EntityUuid or "",
        Template = "",
        Stats = "",
        Amount = 1,
        Slot = "",
    }

    local visual = safe(function() return itemEntity.GameObjectVisual end)
    if visual then
        item.Template = visual.RootTemplateId or ""
    end
    
    local data = safe(function() return itemEntity.Data end)
    if data then
        item.Stats = data.StatsId or ""
    end
    
    local itm = safe(function() return itemEntity.Item end)
    if itm then
        item.Amount = itm.Amount or 1
    end

    return item
end

--- Lê o que o personagem está vestindo.
--- Devolve o mapa slot -> item e o mapa reverso uuid do item -> slot, usado
--- para marcar os mesmos itens quando eles reaparecem na varredura do inventário.
local function ReadEquipment(uuid)
    local bySlot = {}
    local slotOf = {}

    for _, slot in ipairs(EQUIPMENT_SLOTS) do
        local itemUuid = safe(function() return Osi.GetEquippedItem(uuid, slot) end)
        if itemUuid and itemUuid ~= "" then
            local item = ReadItem(safe(function() return Ext.Entity.Get(itemUuid) end))
            if item then
                item.Slot = slot
                bySlot[slot] = item
                slotOf[item.UUID] = slot
            end
        end
    end

    return bySlot, slotOf
end

-- ---------------------------------------------------------------------------
-- Stats de build
-- ---------------------------------------------------------------------------

--- Lê os seis atributos.
--- O array do componente Stats pode ter um slot inicial não usado, então o
--- deslocamento é calculado pelo tamanho em vez de fixado.
local function ReadAbilities(uuid, entity)
    local abilities = {}

    local raw = safe(function() return entity.Stats.Abilities end)
    if type(raw) == "table" and #raw >= #ABILITY_NAMES then
        local offset = #raw - #ABILITY_NAMES
        for i, name in ipairs(ABILITY_NAMES) do
            local value = raw[i + offset]
            if type(value) == "number" then
                abilities[name] = value
            end
        end
    end

    -- Rota Osiris, caso o componente não esteja exposto nesta versão.
    if next(abilities) == nil then
        for _, name in ipairs(ABILITY_NAMES) do
            local value = safe(function() return Osi.GetAbility(uuid, name) end)
            if type(value) == "number" then
                abilities[name] = value
            end
        end
    end

    return abilities
end

--- Lê pontos de vida e classe de armadura.
local function ReadVitals(uuid, entity)
    return {
        Hp = firstOf({
            function() return entity.Health.Hp end,
            function() return Osi.GetHitpoints(uuid) end,
        }),
        MaxHp = firstOf({
            function() return entity.Health.MaxHp end,
            function() return Osi.GetMaxHitpoints(uuid) end,
        }),
        TemporaryHp = firstOf({
            function() return entity.Health.TemporaryHp end,
        }),
        ArmorClass = firstOf({
            function() return entity.Health.AC end,
            function() return entity.Stats.ArmorClass end,
            function() return entity.Stats.AC end,
            function() return entity.BaseStats.ArmorClass end,
        }),
        ProficiencyBonus = firstOf({
            function() return entity.Stats.ProficiencyBonus end,
        }),
        SpellCastingAbility = firstOf({
            function() return tostring(entity.Stats.SpellCastingAbility) end,
        }),
    }
end

--- Recursos de ação: spell slots, ki points, superiority dice, channel divinity.
--- O mapa vem indexado pelo UUID do recurso; Ext.StaticData resolve o nome.
local function ReadActionResources(entity)
    local resources = {}

    local raw = safe(function() return entity.ActionResources.Resources end)
    if not raw then
        return resources
    end

    for resourceUuid, entries in pairs(raw) do
        local name = safe(function()
            return Ext.StaticData.Get(resourceUuid, "ActionResource").Name
        end) or tostring(resourceUuid)

        if entries then
            safe(function()
                for _, entry in pairs(entries) do
                    local maxAmount = safe(function() return entry.MaxAmount end)
                    if type(maxAmount) == "number" and maxAmount > 0 then
                        table.insert(resources, {
                            Name = name,
                            Level = safe(function() return entry.Level end) or 0,
                            Amount = safe(function() return entry.Amount end) or 0,
                            MaxAmount = maxAmount,
                        })
                    end
                end
            end)
        end
    end

    return resources
end

--- Passivas ativas: feats, features de classe e bônus concedidos por itens.
local function ReadPassives(entity)
    local passives = {}

    local container = firstOf({
        function() return entity.PassiveContainer.Passives end,
        function() return entity.Passive.Passives end,
    })
    if not container then
        return passives
    end

    for _, handle in ipairs(container) do
        local id = firstOf({
            function() return Ext.Entity.Get(handle).Passive.PassiveId end,
            function() return handle.Passive.PassiveId end,
        })
        if type(id) == "string" and id ~= "" then
            table.insert(passives, id)
        end
    end

    return passives
end

local function ConvertArray(arr)
    local t = {}
    if arr then
        safe(function()
            for _, v in pairs(arr) do
                table.insert(t, tostring(v))
            end
        end)
    end
    return t
end

--- Proficiências de perícia e de arma/armadura.
local function ReadProficiencies(entity)
    return {
        Skills = ConvertArray(firstOf({
            function() return entity.Stats.Skills end,
        })),
        Flags = ConvertArray(firstOf({
            function() return entity.Proficiency.Flags end,
            function() return entity.ProficiencyGroup.Flags end,
        })),
    }
end

--- Resistências a dano.
local function ReadResistances(entity)
    return ConvertArray(firstOf({
        function() return entity.Resistances.Resistances end,
    }))
end

--- Tags de história, raça, origens, etc.
local function ReadTags(entity)
    local tags = {}
    local raw = safe(function() return entity.Tag.Tags end)
    if not raw then return tags end
    
    safe(function()
        for _, tagUuid in pairs(raw) do
            local name = safe(function()
                return Ext.StaticData.Get(tagUuid, "Tag").Name
            end) or tostring(tagUuid)
            table.insert(tags, name)
        end
    end)
    return tags
end

--- Buffs e Debuffs atuais (Status)
local function ReadStatuses(entity)
    local statuses = {}
    local raw = firstOf({
        function() return entity.StatusContainer.Statuses end,
        function() return entity.ServerStatus.Statuses end,
    })
    if not raw then return statuses end
    
    safe(function()
        for k, v in pairs(raw) do
            local statusId = firstOf({
                function() if type(v) == "string" and v ~= "" then return v end end,
                function() if type(k) == "string" and k ~= "" and not k:match("^Entity") then return k end end,
                function() return Ext.Entity.Get(v).Status.StatusId end,
                function() return v.StatusId end,
                function() return v.Status.StatusId end,
            })
            if type(statusId) == "string" and statusId ~= "" then
                table.insert(statuses, statusId)
            end
        end
    end)
    return statuses
end

--- Coordenadas no mundo [X, Y, Z]
local function ReadPosition(entity)
    local pos = safe(function() return entity.Transform.Transform.Translate end)
    if pos then
        return { pos[1] or 0, pos[2] or 0, pos[3] or 0 }
    end
    return nil
end

--- Classes e Níveis
local function ReadClasses(entity)
    local classes = {}
    local raw = safe(function() return entity.Classes.Classes end)
    if not raw then return classes end

    safe(function()
        for _, classId in pairs(raw) do
            local name = safe(function() return Ext.StaticData.Get(classId, "ClassDescription").Name end) or tostring(classId)
            table.insert(classes, name)
        end
    end)
    return classes
end

--- Magias Preparadas
local function ReadSpells(entity)
    local spells = {}
    local rawPrepares = safe(function() return entity.SpellBookPrepares.PreparedSpells end)
    if rawPrepares then
        safe(function()
            for _, spellId in pairs(rawPrepares) do
                table.insert(spells, tostring(spellId))
            end
        end)
    end
    return spells
end

--- Estatísticas de História e RP
local function ReadStoryStats(entity)
    local story = {
        Experience = safe(function() return entity.Experience.TotalExperience end) or 0,
        Background = safe(function() return entity.Background.Background end) or "",
        God = safe(function() return entity.God.God end) or "",
        TadpolePowers = {},
        Attitudes = {}
    }

    local rawPowers = safe(function() return entity.TadpolePowers.Powers end)
    if rawPowers then
        safe(function()
            for _, power in pairs(rawPowers) do
                table.insert(story.TadpolePowers, tostring(power))
            end
        end)
    end

    local rawAttitudes = safe(function() return entity.AttitudesToPlayers.Attitudes end)
    if rawAttitudes then
        safe(function()
            for k, v in pairs(rawAttitudes) do
                story.Attitudes[tostring(k)] = v
            end
        end)
    end

    return story
end


-- ---------------------------------------------------------------------------
-- Snapshot do personagem
-- ---------------------------------------------------------------------------

--- Monta o snapshot completo de um personagem jogável.
local function ReadCharacter(uuid)
    local entity = safe(function() return Ext.Entity.Get(uuid) end)
    if not entity then
        return nil
    end

    local equipment, slotOf = ReadEquipment(uuid)
    local proficiencies = ReadProficiencies(entity)

    local char = {
        UUID = uuid,
        -- Nome traduzido: serve para exibição, não como chave de join.
        DisplayName = safe(function() return Osi.GetDisplayName(uuid) end) or "",
        -- Formato "S_Player_Laezel_<guid>". O lado Python extrai o Origin daqui
        -- para casar com o SaveInfo.json, que não expõe UUID.
        Template = safe(function() return Osi.GetTemplate(uuid) end) or "",
        Abilities = ReadAbilities(uuid, entity),
        Vitals = ReadVitals(uuid, entity),
        ActionResources = ReadActionResources(entity),
        Passives = ReadPassives(entity),
        Tags = ReadTags(entity),
        Statuses = ReadStatuses(entity),
        Position = ReadPosition(entity),
        Classes = ReadClasses(entity),
        Spells = ReadSpells(entity),
        StoryStats = ReadStoryStats(entity),
        Skills = proficiencies.Skills,
        ProficiencyFlags = proficiencies.Flags,
        Resistances = ReadResistances(entity),
        Equipment = equipment,
        Items = {},
    }

    local invOwner = safe(function() return entity.InventoryOwner end)
    if invOwner and invOwner.Inventories then
        for _, inventoryHandle in ipairs(invOwner.Inventories) do
            local invEntity = safe(function() return Ext.Entity.Get(inventoryHandle) end)
            local inventory = safe(function() return invEntity.Inventory end)
            if invEntity and inventory and inventory.Items then
                for _, itemHandle in ipairs(inventory.Items) do
                    local itemEnt = safe(function() return Ext.Entity.Get(itemHandle) end)
                    local item = ReadItem(itemEnt)
                    if item then
                        item.Slot = slotOf[item.UUID] or ""
                        table.insert(char.Items, item)
                    end
                end
            end
        end
    end

    return char
end

--- Resume quais blocos de dados realmente resolveram, para diagnosticar
--- diferenças de API sem precisar inspecionar o JSON inteiro.
local function Diagnose(characters)
    local resolved = {
        Abilities = 0,
        MaxHp = 0,
        ArmorClass = 0,
        ActionResources = 0,
        Passives = 0,
        Skills = 0,
        Resistances = 0,
        Equipment = 0,
        Tags = 0,
        Statuses = 0,
        Position = 0,
        Classes = 0,
        Spells = 0,
        StoryStats = 0,
    }

    for _, char in ipairs(characters) do
        if countKeys(char.Abilities) > 0 then resolved.Abilities = resolved.Abilities + 1 end
        if char.Vitals.MaxHp ~= nil then resolved.MaxHp = resolved.MaxHp + 1 end
        if char.Vitals.ArmorClass ~= nil then resolved.ArmorClass = resolved.ArmorClass + 1 end
        if #char.ActionResources > 0 then resolved.ActionResources = resolved.ActionResources + 1 end
        if #char.Passives > 0 then resolved.Passives = resolved.Passives + 1 end
        if countKeys(char.Skills) > 0 then resolved.Skills = resolved.Skills + 1 end
        if countKeys(char.Resistances) > 0 then resolved.Resistances = resolved.Resistances + 1 end
        if countKeys(char.Equipment) > 0 then resolved.Equipment = resolved.Equipment + 1 end
        if #char.Tags > 0 then resolved.Tags = resolved.Tags + 1 end
        if #char.Statuses > 0 then resolved.Statuses = resolved.Statuses + 1 end
        if char.Position ~= nil then resolved.Position = resolved.Position + 1 end
        if #char.Classes > 0 then resolved.Classes = resolved.Classes + 1 end
        if #char.Spells > 0 then resolved.Spells = resolved.Spells + 1 end
        if char.StoryStats.Experience > 0 then resolved.StoryStats = resolved.StoryStats + 1 end
    end

    resolved.PartySize = #characters
    return resolved
end

--- Último payload gravado, usado para evitar reescrever conteúdo idêntico.
local lastPayload = nil

--- Monta o snapshot da party e grava em disco.
--- Só escreve quando o conteúdo mudou, ou quando force é verdadeiro.
--- Devolve false quando a party ainda não está disponível.
local function ExportPartySnapshot(force)
    local players = firstOf({
        function() return Osi.DB_Players:Get(nil) end,
        function() return Osi.DB_Avatars:Get(nil) end,
        function() return Osi.DB_IsPlayer:Get(nil) end,
    })
    if not players then
        Ext.Utils.Print("[BroPilot DEBUG] Todas as consultas de DB falharam (DB_Players, DB_Avatars).")
        return false
    elseif #players == 0 then
        Ext.Utils.Print("[BroPilot DEBUG] DB_IsPlayer retornou vazio (nenhum jogador).")
        return false
    end

    Ext.Utils.Print("[BroPilot DEBUG] Encontrou " .. tostring(#players) .. " jogadores na base.")

    local characters = {}
    for _, player in ipairs(players) do
        Ext.Utils.Print("[BroPilot DEBUG] Lendo personagem UUID: " .. tostring(player[1]))
        local char = ReadCharacter(player[1])
        if char then
            table.insert(characters, char)
        else
            Ext.Utils.Print("[BroPilot DEBUG] ReadCharacter retornou nil para: " .. tostring(player[1]))
        end
    end

    if #characters == 0 then
        Ext.Utils.Print("[BroPilot DEBUG] Falha: Nenhum personagem lido com sucesso.")
        return false
    end

    local hostUuid = characters[1].UUID
    local worldContext = {
        Region = safe(function() return Osi.GetRegion(hostUuid) end) or "Unknown",
        IsAtCamp = safe(function() return Osi.IsAtCamp(hostUuid) == 1 end) or false,
        InCombat = false,
        InDialog = false,
        DialogId = "",
    }

    local hostEntity = safe(function() return Ext.Entity.Get(hostUuid) end)
    if hostEntity then
        local inCombat = safe(function() return hostEntity.TurnBased ~= nil or hostEntity.CombatParticipant ~= nil end)
        if inCombat then
            worldContext.InCombat = true
        end
        
        local dialogState = safe(function() return hostEntity.DialogState end)
        if dialogState then
            worldContext.InDialog = true
            worldContext.DialogId = safe(function() return dialogState.DialogId end) or ""
        end
    end

    local payload = Ext.Json.Stringify({
        SchemaVersion = SCHEMA_VERSION,
        Diagnostics = Diagnose(characters),
        WorldContext = worldContext,
        Characters = characters,
    })

    if payload == lastPayload and not force then
        return true
    end

    Ext.IO.SaveFile(EXPORT_FILE, payload)
    lastPayload = payload
    Ext.Utils.Print(string.format("[BroPilot] Snapshot exportado: %d personagens.", #characters))
    return true
end

-- ---------------------------------------------------------------------------
-- Sondagem de API
-- ---------------------------------------------------------------------------

--- Lista os componentes e campos visíveis de um personagem.
--- Serve para fechar os nomes exatos de API em uma versão específica do
--- Script Extender, quando um bloco de stats voltar vazio.
local function ProbeCharacter(uuid)
    local entity = safe(function() return Ext.Entity.Get(uuid) end)
    if not entity then
        return nil
    end

    local components = firstOf({
        function() return entity:GetAllComponents() end,
        function() return entity:GetAllComponentNames() end,
    })
    if type(components) ~= "table" then
        return nil
    end

    local report = {}
    for key, value in pairs(components) do
        -- GetAllComponents devolve nome -> componente; GetAllComponentNames
        -- devolve um array de nomes. Os dois formatos caem aqui.
        local name = type(value) == "string" and value or tostring(key)
        local fields = {}

        if type(value) ~= "string" then
            safe(function()
                for field in pairs(value) do
                    table.insert(fields, tostring(field))
                end
            end)
        end

        table.sort(fields)
        report[name] = fields
    end

    return report
end

-- ---------------------------------------------------------------------------
-- Agendamento
-- ---------------------------------------------------------------------------

local ticks = 0

Ext.Events.Tick:Subscribe(function()
    ticks = ticks + 1
    if ticks < EXPORT_INTERVAL_TICKS then
        return
    end
    ticks = 0
    ExportPartySnapshot(false)
end)

Ext.Events.SessionLoaded:Subscribe(function()
    -- O snapshot da sessão anterior não vale mais: força a próxima gravação.
    lastPayload = nil
    -- Primeira tentativa cerca de um segundo após o carregamento.
    ticks = EXPORT_INTERVAL_TICKS - 60
end)

--- Força um export imediato. No console do Script Extender: !bropilot_export
Ext.RegisterConsoleCommand("bropilot_export", function()
    if not ExportPartySnapshot(true) then
        Ext.Utils.Print("[BroPilot] Party indisponível; export ignorado.")
    end
end)

--- Grava bropilot_probe.json com os componentes do personagem controlado.
--- No console do Script Extender: !bropilot_probe
Ext.RegisterConsoleCommand("bropilot_probe", function()
    local host = firstOf({
        function() return Osi.GetHostCharacter() end,
        function() return Osi.DB_IsPlayer:Get(nil)[1][1] end,
    })
    if not host then
        Ext.Utils.Print("[BroPilot] Nenhum personagem para sondar.")
        return
    end

    local report = ProbeCharacter(host)
    if not report then
        Ext.Utils.Print("[BroPilot] Sondagem indisponível nesta versão do Script Extender.")
        return
    end

    Ext.IO.SaveFile(PROBE_FILE, Ext.Json.Stringify({
        Character = host,
        Components = report,
    }))
    Ext.Utils.Print("[BroPilot] Componentes salvos em " .. PROBE_FILE)
end)
