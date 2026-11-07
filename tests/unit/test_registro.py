"""US-19 y US-20: registro de estudiantes y tutores con correo (sin contraseña)."""

from datetime import time

import pytest

from src.application.servicios_estudiantes import ServicioEstudiantes
from src.domain.comun import DatosInvalidos, NoEncontrado, RecursoNoDisponible, Rol
from src.domain.registro import (
    Cuenta,
    TipoCuenta,
    normalizar_correo,
    siguiente_id_estudiante,
    siguiente_id_tutor,
)
from src.domain.sesiones.modelo import BloqueDisponibilidad, Modalidad
from tests.conftest import solicitud


@pytest.fixture
def registro(uow):
    return ServicioEstudiantes(uow)


def test_correo_se_normaliza_y_valida():
    assert normalizar_correo("  Ana@Correo.COM ") == "ana@correo.com"
    for malo in ["", "ana", "ana@correo", "ana @correo.com", "@correo.com"]:
        with pytest.raises(DatosInvalidos):
            normalizar_correo(malo)
    cuenta = Cuenta("ANA@correo.com", "AUL-E001", "ESTUDIANTE")
    assert cuenta.id == "ana@correo.com" and cuenta.tipo is TipoCuenta.ESTUDIANTE


def test_ids_nuevos_no_chocan_con_el_paquete_del_docente():
    assert siguiente_id_estudiante(["AUL-C001", "AUL-C040"]) == "AUL-E001"
    assert siguiente_id_estudiante(["AUL-C001", "AUL-E001", "AUL-E007"]) == "AUL-E008"
    assert siguiente_id_tutor(["AUL-T01", "AUL-T05"]) == "AUL-T06"


def test_registrar_crea_estudiante_y_cuenta(registro, uow):
    antes = uow.confirmaciones
    r = registro.registrar("  Ana   López ", "Ana@Correo.com", "Monterrey")
    assert r.estudiante.id == "AUL-E001" and r.estudiante.nombre == "Ana López"
    assert r.correo == "ana@correo.com" and r.estudiante.activo
    assert uow.estudiantes.obtener("AUL-E001").ciudad == "Monterrey"
    assert uow.cuentas.obtener("ana@correo.com").usuario_id == "AUL-E001"
    assert uow.confirmaciones == antes + 1
    assert registro.registrar("Luis", "luis@correo.com", "Apodaca").estudiante.id == "AUL-E002"


def test_correo_repetido_responde_conflicto(registro):
    registro.registrar("Ana López", "ana@correo.com", "Monterrey")
    with pytest.raises(RecursoNoDisponible, match="Ya existe una cuenta"):
        registro.registrar("Otra Ana", "ANA@correo.com", "Apodaca")


@pytest.mark.parametrize(
    ("nombre", "correo", "ciudad"),
    [("A", "a@b.com", "Monterrey"), ("Ana", "no-es-correo", "Monterrey"), ("Ana", "a@b.com", " ")],
)
def test_datos_invalidos(registro, uow, nombre, correo, ciudad):
    with pytest.raises(DatosInvalidos):
        registro.registrar(nombre, correo, ciudad)
    assert uow.estudiantes.obtener("AUL-E001") is None


def test_acceder_con_correo(registro):
    registro.registrar("Ana López", "ana@correo.com", "Monterrey")
    assert registro.acceder(" ANA@correo.com").estudiante.id == "AUL-E001"
    with pytest.raises(NoEncontrado):
        registro.acceder("nadie@correo.com")


def test_solo_estudiantes_existentes_pueden_reservar(registro, servicio):
    with pytest.raises(NoEncontrado, match="AUL-X999"):
        servicio.reservar(Rol.ESTUDIANTE, solicitud(estudiante="AUL-X999"))
    nuevo = registro.registrar("Ana López", "ana@correo.com", "Monterrey").estudiante
    sesion = servicio.reservar(Rol.ESTUDIANTE, solicitud(estudiante=nuevo.id))
    assert sesion.estudiante_id == "AUL-E001"


# --------------------------------------------------------------------------- #
# US-20: tutores
# --------------------------------------------------------------------------- #
JUEVES_MANANA = [BloqueDisponibilidad(3, time(8, 0), time(14, 0))]


def nuevo_tutor(registro, correo="carlos@correo.com", **cambios):
    datos = {
        "nombre": "Carlos Méndez",
        "correo": correo,
        "materias": ["Química"],
        "modalidades": [Modalidad.EN_LINEA],
        "zona": "Monterrey",
        "bloques": JUEVES_MANANA,
    }
    datos.update(cambios)
    return registro.registrar_tutor(**datos)


def test_registrar_tutor_crea_tutor_y_cuenta(registro, uow):
    r = nuevo_tutor(registro)
    assert r.tutor.id == "AUL-T06" and r.tutor.imparte("química")
    assert uow.tutores.obtener("AUL-T06").bloques == tuple(JUEVES_MANANA)
    cuenta = uow.cuentas.obtener("carlos@correo.com")
    assert cuenta.usuario_id == "AUL-T06" and cuenta.tipo is TipoCuenta.TUTOR
    assert registro.acceder_tutor("CARLOS@correo.com").tutor.nombre == "Carlos Méndez"


@pytest.mark.parametrize(
    "cambios",
    [{"materias": []}, {"modalidades": []}, {"bloques": []}, {"zona": ""}, {"nombre": "C"}],
)
def test_tutor_con_datos_invalidos(registro, uow, cambios):
    with pytest.raises(DatosInvalidos):
        nuevo_tutor(registro, **cambios)
    assert uow.tutores.obtener("AUL-T06") is None


def test_correo_unico_entre_estudiantes_y_tutores(registro):
    registro.registrar("Ana López", "ana@correo.com", "Monterrey")
    with pytest.raises(RecursoNoDisponible):
        nuevo_tutor(registro, correo="ana@correo.com")
    nuevo_tutor(registro)
    with pytest.raises(NoEncontrado):
        registro.acceder("carlos@correo.com")  # es cuenta de tutor, no de estudiante
    with pytest.raises(NoEncontrado):
        registro.acceder_tutor("ana@correo.com")


def test_tutor_nuevo_entra_en_la_asignacion(registro, servicio):
    """Nadie más imparte Química: la reserva del jueves 10:00 se le asigna al tutor nuevo."""
    nuevo_tutor(registro)
    sesion = servicio.reservar(Rol.ESTUDIANTE, solicitud(materia="Química"))
    assert sesion.tutor_id == "AUL-T06"
