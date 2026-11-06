"""Value Objects, Specification base y máquina de estados genérica."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from decimal import Decimal
from enum import Enum

import pytest

from src.domain.comun import (
    DatosInvalidos,
    Dinero,
    PermisoDenegado,
    Rol,
    TransicionInvalida,
    a_utc,
    exigir_rol,
)
from src.domain.especificacion import Especificacion
from src.domain.maquina_estados import MaquinaEstados


class TestDinero:
    def test_redondea_a_centavos(self):
        assert Dinero.mxn("10.005").monto == Decimal("10.01")

    def test_rechaza_float(self):
        with pytest.raises(DatosInvalidos):
            Dinero(0.1)  # type: ignore[arg-type]
        with pytest.raises(DatosInvalidos):
            Dinero.mxn(0.1)  # type: ignore[arg-type]

    def test_rechaza_negativo_y_otra_moneda(self):
        with pytest.raises(DatosInvalidos):
            Dinero.mxn("-1")
        with pytest.raises(DatosInvalidos):
            Dinero(Decimal("1"), "USD")

    def test_es_inmutable_y_compara_por_valor(self):
        a = Dinero.mxn("200")
        assert a == Dinero.mxn("200.00")
        with pytest.raises(FrozenInstanceError):
            a.monto = Decimal(1)  # type: ignore[misc]

    def test_aritmetica_exacta(self):
        assert Dinero.mxn("0.1") + Dinero.mxn("0.2") == Dinero.mxn("0.3")
        assert Dinero.mxn("200") - Dinero.mxn("40") == Dinero.mxn("160")
        assert Dinero.mxn("405") * 3 == Dinero.mxn("1215")
        assert Dinero.mxn("200").porcentaje(Decimal("20")) == Dinero.mxn("40")
        assert str(Dinero.mxn("5")) == "5.00 MXN"

    def test_no_multiplica_por_no_entero(self):
        with pytest.raises(DatosInvalidos):
            Dinero.mxn("1") * 1.5  # type: ignore[operator]

    def test_no_suma_otro_tipo(self):
        with pytest.raises(DatosInvalidos):
            Dinero.mxn("1") + 1  # type: ignore[operator]


def test_a_utc_exige_zona_horaria():
    with pytest.raises(DatosInvalidos):
        a_utc(datetime(2026, 1, 1, 10, 0))
    with pytest.raises(DatosInvalidos):
        a_utc("2026-01-01")  # type: ignore[arg-type]


def test_exigir_rol():
    exigir_rol(Rol.SOPORTE, Rol.SOPORTE)
    with pytest.raises(PermisoDenegado, match="SOPORTE"):
        exigir_rol(Rol.ESTUDIANTE, Rol.SOPORTE)


class EsPar(Especificacion[int]):
    descripcion = "es par"

    def es_satisfecha_por(self, n: int) -> bool:
        return n % 2 == 0


class MayorQueDiez(Especificacion[int]):
    descripcion = "mayor que 10"

    def es_satisfecha_por(self, n: int) -> bool:
        return n > 10


class TestEspecificacion:
    def test_and_or_not(self):
        y, o, no = EsPar() & MayorQueDiez(), EsPar() | MayorQueDiez(), ~EsPar()
        assert y.es_satisfecha_por(12) and not y.es_satisfecha_por(8)
        assert o.es_satisfecha_por(8) and o.es_satisfecha_por(11) and not o.es_satisfecha_por(7)
        assert no.es_satisfecha_por(7) and not no.es_satisfecha_por(8)

    def test_incumplidas_lista_las_reglas_que_fallan(self):
        y = EsPar() & MayorQueDiez()
        assert y.incumplidas(7) == ["es par", "mayor que 10"]
        assert y.incumplidas(12) == []
        assert (EsPar() | MayorQueDiez()).incumplidas(7) == ["(es par OR mayor que 10)"]
        assert (~EsPar()).incumplidas(8) == ["NOT es par"]

    def test_describir(self):
        assert (EsPar() & ~MayorQueDiez()).describir() == "es par AND NOT mayor que 10"


class Luz(Enum):
    ROJO = "ROJO"
    VERDE = "VERDE"


def test_maquina_estados():
    maquina = MaquinaEstados("Semaforo", {(Luz.ROJO, "avanzar"): Luz.VERDE})
    assert maquina.destino(Luz.ROJO, "avanzar") is Luz.VERDE
    assert maquina.acciones_desde(Luz.ROJO) == ["avanzar"]
    assert maquina.es_final(Luz.VERDE)
    with pytest.raises(TransicionInvalida, match="VERDE"):
        maquina.destino(Luz.VERDE, "avanzar")
