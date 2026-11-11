"""US-19: registro de estudiantes con correo (sin contraseña)."""

import pytest

from src.application.servicios_estudiantes import ServicioEstudiantes
from src.domain.comun import DatosInvalidos, NoEncontrado, RecursoNoDisponible, Rol
from src.domain.registro import CuentaEstudiante, normalizar_correo, siguiente_id_estudiante
from tests.conftest import solicitud


@pytest.fixture
def registro(uow):
    return ServicioEstudiantes(uow)


def test_correo_se_normaliza_y_valida():
    assert normalizar_correo("  Ana@Correo.COM ") == "ana@correo.com"
    for malo in ["", "ana", "ana@correo", "ana @correo.com", "@correo.com"]:
        with pytest.raises(DatosInvalidos):
            normalizar_correo(malo)
    assert CuentaEstudiante("ANA@correo.com", "AUL-E001").id == "ana@correo.com"


def test_ids_nuevos_no_chocan_con_el_paquete_del_docente():
    assert siguiente_id_estudiante(["AUL-C001", "AUL-C040"]) == "AUL-E001"
    assert siguiente_id_estudiante(["AUL-C001", "AUL-E001", "AUL-E007"]) == "AUL-E008"


def test_registrar_crea_estudiante_y_cuenta(registro, uow):
    antes = uow.confirmaciones
    r = registro.registrar("  Ana   López ", "Ana@Correo.com", "Monterrey")
    assert r.estudiante.id == "AUL-E001" and r.estudiante.nombre == "Ana López"
    assert r.correo == "ana@correo.com" and r.estudiante.activo
    assert uow.estudiantes.obtener("AUL-E001").ciudad == "Monterrey"
    assert uow.cuentas.obtener("ana@correo.com").estudiante_id == "AUL-E001"
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
