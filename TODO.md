# TODO List (Roadmap de Implementación)

## Fase 1: Los Cimientos (Infrastructure & Data)
- [x] **Docker Compose**: Levantar un contenedor Postgres con la extensión pgvector activada.
- [x] **Schema Definition (SQLModel)**: Definir tablas:
    - [x] Notes (id, content, summary, created_at, embedding).
    - [x] Links (source_id, target_id, relation_type, reason).
- [x] **DB Connection**: Script de Python para conectar y hacer "Health Check".

## Fase 2: El Cerebro (LangGraph & Logic)
- [x] **Embedding Service**: Función simple que toma texto y devuelve vector (AWS Bedrock Titan).
- [x] **Ingest Agent (Grafo Simple)**:
    - [x] Nodo 1: Recibe -> Limpia -> Embed.
    - [x] Nodo 2: Guarda en Postgres.
- [x] **Linking Agent (La magia)**:
    - [x] Nodo 1: Query Vectorial (trae las 5 notas más parecidas).
    - [x] Nodo 2 (LLM): Decide si hay relación y tipo.
    - [x] Nodo 3: Inserta en tabla Links.

## Fase 3: La Interfaz (CLI con Typer)
- [x] **Comando init**: Crea las tablas en la BD si no existen.
- [x] **Comando add**: Conecta con el Ingest Agent.
- [x] **Comando trace**: Query SQL recursiva/simple. Timeline ASCII/Texto.
