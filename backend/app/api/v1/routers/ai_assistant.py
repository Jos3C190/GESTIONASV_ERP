"""
AI Assistant Router con Amazon Bedrock Guardrails
Integración segura de agente conversacional para GESTIONASV_ERP.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Assistant (Bedrock)"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Mensaje del usuario")


class ChatResponse(BaseModel):
    reply: str
    guardrail_intervened: bool
    details: Optional[Dict[str, Any]] = None


def get_bedrock_runtime_client():
    """
    Obtiene el cliente de Amazon Bedrock Runtime.
    Lee automáticamente credenciales y región desde variables de entorno o rol IAM.
    """
    aws_region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    try:
        return boto3.client("bedrock-runtime", region_name=aws_region)
    except Exception as exc:
        logger.error("ai.bedrock_client_init_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo inicializar la conexión con el servicio de IA."
        )


@router.post("/chat", response_model=ChatResponse)
async def chat_with_erp_agent(payload: ChatRequest) -> ChatResponse:
    """
    Endpoint principal para interactuar con el Asistente de IA del ERP.
    Todas las peticiones pasan a través de Amazon Bedrock Guardrails.
    """
    guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
    guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

    if not guardrail_id:
        logger.error("ai.configuration_missing", detail="BEDROCK_GUARDRAIL_ID not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de asistente de IA no está configurado en este entorno."
        )

    client = get_bedrock_runtime_client()

    logger.info("ai.chat_request_received", length=len(payload.message))

    try:
        response = client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": payload.message}]
                }
            ],
            guardrailConfig={
                "guardrailIdentifier": guardrail_id,
                "guardrailVersion": guardrail_version,
                "trace": "enabled"
            }
        )

        stop_reason = response.get("stopReason")
        output_content = response.get("output", {}).get("message", {}).get("content", [{}])[0].get("text", "")
        
        intervened = (stop_reason == "guardrail_intervened")

        if intervened:
            logger.warn("ai.guardrail_intervened", stop_reason=stop_reason)
        else:
            logger.info("ai.query_processed_successfully")

        return ChatResponse(
            reply=output_content,
            guardrail_intervened=intervened,
            details={
                "model": model_id,
                "stop_reason": stop_reason
            }
        )

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))
        logger.error("ai.bedrock_client_error", code=error_code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error en el servicio de Amazon Bedrock ({error_code})"
        )
    except Exception as exc:
        logger.error("ai.unexpected_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar la solicitud con el asistente de IA."
        )
