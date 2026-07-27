"""Subpacote de RAG: indexação (build) e busca (retriever).

Vector store: LanceDB. Por quê, num projeto local-first:
- Embarcado de verdade — é um diretório em disco, sem processo servidor para
  subir/manter (Chroma no modo persistente também roda embarcado, mas LanceDB é
  mais leve de dependência e nasceu para isso).
- Footprint enxuto casa com "roda na mesma máquina do BG3", onde cada MB de RAM
  e cada dependência disputam espaço com o jogo.
- Formato colunar (Lance) lê rápido sem carregar o índice inteiro na memória.
Trade-off honesto: menos tutoriais/comunidade que o Chroma. Se isso pesar na
prática, o retriever isola o vector store atrás de sua própria interface, então
trocar depois é local a este subpacote.
"""
