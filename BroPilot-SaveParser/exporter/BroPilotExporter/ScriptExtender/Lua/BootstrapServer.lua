local exported = false

local function ExportPartyInventory()
    Ext.Utils.Print("[BroPilot] Tentando exportar inventário...")
    
    local players = nil
    pcall(function()
        players = Osi.DB_IsPlayer:Get(nil)
    end)

    if not players or #players == 0 then
        Ext.Utils.Print("[BroPilot] Osi.DB_IsPlayer ainda não está pronto.")
        return false
    end

    local inventoryData = {}

    for _, player in ipairs(players) do
        local uuid = player[1]
        local entity = Ext.Entity.Get(uuid)
        if entity and entity.InventoryOwner then
            local charData = {
                UUID = uuid,
                Items = {}
            }
            
            if entity.InventoryOwner.Inventories then
                for _, inventoryHandle in ipairs(entity.InventoryOwner.Inventories) do
                    local invEntity = Ext.Entity.Get(inventoryHandle)
                    if invEntity and invEntity.Inventory and invEntity.Inventory.Items then
                        for _, itemHandle in ipairs(invEntity.Inventory.Items) do
                            local itemEntity = Ext.Entity.Get(itemHandle)
                            if itemEntity and itemEntity.Uuid then
                                local itemData = {
                                    UUID = itemEntity.Uuid.EntityUuid or "",
                                    Template = "",
                                    Stats = "",
                                    Amount = 1
                                }
                                
                                if itemEntity.GameObjectVisual then
                                    itemData.Template = itemEntity.GameObjectVisual.RootTemplateId or ""
                                end
                                if itemEntity.Data then
                                    itemData.Stats = itemEntity.Data.StatsId or ""
                                end
                                if itemEntity.Item then
                                    itemData.Amount = itemEntity.Item.Amount or 1
                                end
                                
                                table.insert(charData.Items, itemData)
                            end
                        end
                    end
                end
            end
            table.insert(inventoryData, charData)
        end
    end

    local jsonStr = Ext.Json.Stringify(inventoryData)
    Ext.IO.SaveFile("bropilot_inventory.json", jsonStr)
    Ext.Utils.Print("[BroPilot] SUCESSO! INVENTARIO EXPORTADO PARA bropilot_inventory.json!")
    return true
end

local timer = 0
Ext.Events.Tick:Subscribe(function(e)
    if exported then return end
    timer = timer + 1
    if timer >= 180 then
        timer = 0
        if ExportPartyInventory() then
            exported = true
        end
    end
end)

Ext.Events.SessionLoaded:Subscribe(function()
    exported = false
    timer = 150
end)
