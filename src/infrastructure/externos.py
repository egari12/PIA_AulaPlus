"""Adaptadores de servicios externos: reloj y pasarela de pagos simulada (mock)."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime

from src.domain.comun import Dinero, PagoRechazado, a_utc, ahora_utc
from src.domain.sesiones.modelo import MSG_PAGO_FALLIDO


class RelojSistema:
    def ahora(self) -> datetime:
        return ahora_utc()


class RelojFijo:
    """Reloj controlable para pruebas y demostraciones."""

    def __init__(self, momento: datetime):
        self.momento = a_utc(momento, "momento")

    def ahora(self) -> datetime:
        return self.momento

    def avanzar(self, delta) -> None:
        self.momento = self.momento + delta


@dataclass
class OperacionPago:
    tipo: str
    destino: str
    monto: Dinero
    referencia: str


@dataclass
class PasarelaSimulada:
    """Simula el procesador de pagos. Los estudiantes en 'rechazar' reciben un cobro fallido."""

    rechazar: set[str] = field(default_factory=set)
    operaciones: list[OperacionPago] = field(default_factory=list)
    _folio: itertools.count = field(default_factory=lambda: itertools.count(1), repr=False)

    def _registrar(self, tipo: str, destino: str, monto: Dinero) -> str:
        referencia = f"{tipo[:3].upper()}-{next(self._folio):06d}"
        self.operaciones.append(OperacionPago(tipo, destino, monto, referencia))
        return referencia

    def cobrar(self, estudiante_id: str, monto: Dinero, concepto: str) -> str:
        if estudiante_id in self.rechazar:
            raise PagoRechazado(MSG_PAGO_FALLIDO)
        return self._registrar("cobro", estudiante_id, monto)

    def transferir(self, tutor_id: str, monto: Dinero, concepto: str) -> str:
        return self._registrar("transferencia", tutor_id, monto)

    def reembolsar(self, referencia: str, monto: Dinero) -> str:
        return self._registrar("reembolso", referencia, monto)
