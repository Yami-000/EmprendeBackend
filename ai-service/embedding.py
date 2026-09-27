# -*- coding: utf-8 -*-
"""Contrato unico del embedder: que modelo se usa y como se le da el texto.

POR QUE EXISTE ESTE MODULO
--------------------------
El nombre del modelo estaba escrito a mano en SIETE lugares (ingest.py, api.py y
cinco scripts de medicion). Indexar y consultar con modelos distintos produce
vectores incomparables, y ya paso una vez: ingest.py intentaba nomic-embed-text
(768 dims) con respaldo silencioso a MiniLM (384) mientras api.py usaba siempre
MiniLM, y coincidian por accidente. Con siete copias, la proxima divergencia era
cuestion de tiempo.

Aca vive una sola definicion. Todo lo que embeba texto en el proyecto importa de
aca.

LOS PREFIJOS NO SON DECORACION
------------------------------
Los modelos de la familia E5 se entrenaron con prefijos asimetricos: "query: "
para lo que se busca y "passage: " para lo que esta indexado. Sin ellos el modelo
rinde peor, porque nunca vio texto sin prefijo durante el entrenamiento. Y usar
el prefijo equivocado es peor que no usar ninguno: invierte la asimetria que el
modelo aprendio.

MiniLM no usa prefijos, asi que para el son cadenas vacias. Esa es la razon de
que existan las dos funciones en vez de concatenar a mano en cada sitio: cambiar
de modelo no deberia obligar a recordar siete lugares donde poner un prefijo.
"""

# Iteración 1.14. Debe coincidir en indexación y consulta, siempre.
#
#   all-MiniLM-L6-v2 ........ 384 dims, ventana de 256 tokens
#   multilingual-e5-small ... 384 dims, ventana de 512 tokens
#
# La ventana es la razón del cambio: los fragmentos tienen mediana 382 tokens y
# máximo 495, así que con 256 el 32% del corpus no influía en el retrieval.
# Medido antes del cambio: con la cita dentro de la ventana anclaje@6 acertaba
# 21/23 (91%); fuera, 7/14 (50%). Ver scripts/medir_ventana_embedder.py.
#
# Se eligió el 'small' y no un modelo de ventana mayor (bge-m3 llega a 8192
# tokens) porque mantiene las 384 dimensiones —no cambia el esquema del índice— y
# pesa ~470 MB contra 2,2 GB. Correr en hardware modesto es el objetivo del
# proyecto, no una restricción a superar.
MODEL_NAME = "intfloat/multilingual-e5-small"

# Prefijos que el modelo espera. Vacíos para los modelos que no los usan.
PREFIJO_CONSULTA = "query: "
PREFIJO_PASAJE = "passage: "


def para_consulta(texto: str) -> str:
    """Texto listo para embeber como CONSULTA (lo que el usuario pregunta)."""
    return PREFIJO_CONSULTA + (texto or "")


def para_pasaje(texto: str) -> str:
    """Texto listo para embeber como PASAJE (lo que queda en el índice)."""
    return PREFIJO_PASAJE + (texto or "")
