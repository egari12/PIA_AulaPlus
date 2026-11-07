"""Pruebas de la API REST: códigos 200/201, 402, 403, 404, 409 y 422 y Swagger."""

from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from src.api.main import create_app  # noqa: E402
from src.config import Configuracion  # noqa: E402
from src.infrastructure.externos import PasarelaSimulada, RelojFijo  # noqa: E402
from tests.conftest import AHORA, JUEVES_10  # noqa: E402

ESTUDIANTE = {"X-Rol": "ESTUDIANTE"}
SOPORTE = {"X-Rol": "SOPORTE"}
SISTEMA = {"X-Rol": "SISTEMA"}
ADMIN = {"X-Rol": "ADMINISTRADOR"}


@pytest.fixture
def cliente():
    config = Configuracion(database_url="sqlite+pysqlite:///:memory:", sembrar_datos=True)
    app = create_app(config, reloj=RelojFijo(AHORA), pasarela=PasarelaSimulada(rechazar={"AUL-C040"}))
    with TestClient(app) as c:
        yield c
    app.state.engine.dispose()


def reserva(estudiante="AUL-C001", inicio=JUEVES_10, materia="Python"):
    return {"estudiante_id": estudiante, "materia": materia, "tema": "Funciones",
            "modalidad": "EN_LINEA", "inicio": inicio.isoformat()}


def crear_sesion(cliente, **kw):
    r = cliente.post("/sesiones", json=reserva(**kw), headers=ESTUDIANTE)
    assert r.status_code == 201, r.text
    return r.json()


def test_salud_y_swagger(cliente):
    assert cliente.get("/salud").json()["estado"] == "ok"
    assert cliente.get("/docs").status_code == 200
    raiz = cliente.get("/")
    assert raiz.status_code == 200 and "text/html" in raiz.headers["content-type"]
    assert "AulaPlus" in raiz.text and "/docs" in raiz.text
    rutas = cliente.get("/openapi.json").json()["paths"]
    assert "/sesiones" in rutas and "/inscripciones/{inscripcion_id}/validar" in rutas


def test_reserva_201_y_consulta(cliente):
    sesion = crear_sesion(cliente)
    assert sesion["estado"] == "CONFIRMADA" and sesion["tutor_id"] == "AUL-T01"
    assert sesion["precio"] == "200.00"
    r = cliente.get(f"/sesiones/{sesion['id']}")
    assert r.status_code == 200
    eventos = cliente.get(f"/sesiones/{sesion['id']}/eventos").json()
    assert [e["nombre"] for e in eventos] == ["SesionReservada"]
    assert len(cliente.get("/sesiones", params={"estado": "CONFIRMADA"}).json()) == 1


def test_errores_de_reserva(cliente):
    tarde = cliente.post("/sesiones", json=reserva(inicio=AHORA + timedelta(hours=5)), headers=ESTUDIANTE)
    assert tarde.status_code == 422 and "48 horas" in tarde.json()["detalle"]
    sin_tutor = cliente.post("/sesiones", json=reserva(materia="Química"), headers=ESTUDIANTE)
    assert sin_tutor.status_code == 409
    pago = cliente.post("/sesiones", json=reserva(estudiante="AUL-C040"), headers=ESTUDIANTE)
    assert pago.status_code == 402
    assert cliente.post("/sesiones", json=reserva(), headers=SOPORTE).status_code == 403
    assert cliente.post("/sesiones", json=reserva()).status_code == 422  # falta X-Rol
    assert cliente.get("/sesiones/NO-EXISTE").status_code == 404


def test_grabacion_liquidacion(cliente):
    sesion = crear_sesion(cliente)
    fin = (JUEVES_10 + timedelta(minutes=90)).isoformat()
    r = cliente.post(f"/sesiones/{sesion['id']}/grabacion", headers=SISTEMA,
                     json={"url": "https://v/1.mp4", "inicio": JUEVES_10.isoformat(), "fin": fin})
    assert r.status_code == 200 and r.json()["estado"] == "COMPLETADA"
    liq = cliente.post(f"/sesiones/{sesion['id']}/liquidacion", headers=SISTEMA).json()
    assert liq["monto_tutor"] == "160.00" and liq["comision"] == "40.00"
    otra = cliente.post(f"/sesiones/{sesion['id']}/liquidacion", headers=SISTEMA)
    assert otra.status_code == 409


def test_grabacion_corta_reembolsa(cliente):
    sesion = crear_sesion(cliente)
    fin = (JUEVES_10 + timedelta(minutes=30)).isoformat()
    r = cliente.post(f"/sesiones/{sesion['id']}/grabacion", headers=SISTEMA,
                     json={"url": "u", "inicio": JUEVES_10.isoformat(), "fin": fin})
    assert r.json()["estado"] == "REEMBOLSADA"
    liq = cliente.post(f"/sesiones/{sesion['id']}/liquidacion", headers=SISTEMA).json()
    assert liq["estado_pago"] == "No aplicable – reembolso"


def test_cancelacion_solo_soporte(cliente):
    sesion = crear_sesion(cliente)
    cuerpo = {"solicitante": "TUTOR", "motivo": "Viaje", "justificada": False}
    denegado = cliente.post(f"/sesiones/{sesion['id']}/cancelacion", json=cuerpo, headers=ADMIN)
    assert denegado.status_code == 403 and "Solo Soporte" in denegado.json()["detalle"]
    ok = cliente.post(f"/sesiones/{sesion['id']}/cancelacion", json=cuerpo, headers=SOPORTE)
    assert ok.status_code == 200 and ok.json()["estado"] == "CANCELADA"
    reporte = cliente.get("/reportes/cancelaciones-tutores", headers=ADMIN).json()
    assert reporte[0]["tutor_id"] == "AUL-T01" and reporte[0]["cancelaciones"] == 1


def test_calificacion_y_cambios(cliente):
    sesion = crear_sesion(cliente)
    r = cliente.post(f"/sesiones/{sesion['id']}/calificaciones", json={"puntuacion": 5}, headers=ESTUDIANTE)
    assert r.status_code == 409  # todavía no está completada
    r = cliente.post(f"/sesiones/{sesion['id']}/cambios", json={"tipo": "MODALIDAD", "valor": "EN_LINEA"},
                     headers=ESTUDIANTE)
    assert r.status_code == 200 and r.json()["cambio_pendiente"]["tipo"] == "MODALIDAD"
    r = cliente.post(f"/sesiones/{sesion['id']}/cambios/aplicar", headers=SOPORTE)
    assert r.status_code == 200 and r.json()["cambio_pendiente"] is None


def test_tutores_y_politicas(cliente):
    assert len(cliente.get("/tutores").json()) == 5
    assert cliente.get("/tutores/NO").status_code == 404
    bloques = {"bloques": [{"dia_semana": 0, "hora_inicio": "08:00", "hora_fin": "12:00"}]}
    r = cliente.put("/tutores/AUL-T02/disponibilidad", json=bloques, headers={"X-Rol": "TUTOR"})
    assert r.status_code == 200 and len(r.json()["bloques"]) == 1
    assert cliente.put("/politicas/comision", json={"porcentaje": "25"}, headers=SOPORTE).status_code == 403
    r = cliente.put("/politicas/comision", json={"porcentaje": "25"}, headers=ADMIN)
    assert r.status_code == 200 and cliente.get("/politicas").json()["porcentaje_comision"] == "25.00"


def test_reporte_de_sesiones(cliente):
    crear_sesion(cliente)
    params = {"desde": AHORA.isoformat(), "hasta": (AHORA + timedelta(days=7)).isoformat()}
    r = cliente.get("/reportes/sesiones", params=params, headers=ADMIN)
    assert r.status_code == 200 and r.json()["por_estado"]["CONFIRMADA"] == 1


def test_inscripciones_del_paquete(cliente):
    assert len(cliente.get("/estudiantes").json()) == 40
    assert len(cliente.get("/cursos").json()) == 20
    assert len(cliente.get("/inscripciones").json()) == 60
    o001 = cliente.get("/inscripciones/AUL-O001").json()
    assert o001["total"] == "8231.00" and o001["estado"] == "PREINSCRITA"
    assert cliente.post("/inscripciones/AUL-O001/inscribir").status_code == 409  # saltar estado
    assert cliente.post("/inscripciones/AUL-O001/validar").status_code == 200
    assert cliente.post("/inscripciones/AUL-O001/validar").status_code == 409  # repetir
    assert cliente.post("/inscripciones/AUL-O013/validar").status_code == 422  # sin detalle
    assert cliente.post("/inscripciones/AUL-O001/inscribir").json()["estado"] == "INSCRITA"
    assert cliente.post("/inscripciones/AUL-O001/finalizar").json()["estado"] == "FINALIZADA"
    eventos = cliente.get("/inscripciones/AUL-O001/eventos").json()
    assert [e["nombre"] for e in eventos] == ["InscripcionValidada", "InscripcionConfirmada", "InscripcionFinalizada"]
    assert cliente.get("/inscripciones/NO-EXISTE").status_code == 404
    assert "aplica" in cliente.get("/inscripciones/AUL-O001/beneficio").json()
    r = cliente.post("/inscripciones/AUL-O002/cancelar", json={"motivo": "Baja"})
    assert r.json()["estado"] == "CANCELADA"


def test_crear_inscripcion(cliente):
    cuerpo = {"estudiante_id": "AUL-C005", "lineas": [{"curso_id": "AUL-P001", "cantidad": 2}]}
    r = cliente.post("/inscripciones", json=cuerpo)
    assert r.status_code == 201 and r.json()["total"] == "810.00"
    cuerpo["lineas"][0]["cantidad"] = 0
    assert cliente.post("/inscripciones", json=cuerpo).status_code == 422


def test_registro_de_estudiante_y_acceso_us19(cliente):
    ana = {"nombre": "Ana López", "correo": "ana@correo.com", "ciudad": "Monterrey"}
    r = cliente.post("/estudiantes", json=ana)
    assert r.status_code == 201, r.text
    assert r.json() == {"id": "AUL-E001", "nombre": "Ana López", "ciudad": "Monterrey", "correo": "ana@correo.com"}
    repetido = cliente.post("/estudiantes", json={**ana, "correo": "ANA@correo.com"})
    assert repetido.status_code == 409 and repetido.json()["error"] == "RecursoNoDisponible"
    assert cliente.post("/estudiantes", json={**ana, "correo": "no-es-correo"}).status_code == 422
    assert cliente.post("/estudiantes/acceso", json={"correo": " Ana@Correo.com"}).json()["id"] == "AUL-E001"
    assert cliente.post("/estudiantes/acceso", json={"correo": "nadie@correo.com"}).status_code == 404
    assert any(e["id"] == "AUL-E001" for e in cliente.get("/estudiantes").json())
    assert crear_sesion(cliente, estudiante="AUL-E001")["estudiante_id"] == "AUL-E001"


def test_reserva_de_estudiante_inexistente_404(cliente):
    r = cliente.post("/sesiones", json=reserva(estudiante="AUL-X999"), headers=ESTUDIANTE)
    assert r.status_code == 404 and "AUL-X999" in r.json()["detalle"]


def test_registro_de_tutor_y_asignacion_us20(cliente):
    carlos = {
        "nombre": "Carlos Méndez",
        "correo": "carlos@correo.com",
        "materias": ["Química"],
        "modalidades": ["EN_LINEA"],
        "zona": "Monterrey",
        "bloques": [{"dia_semana": 3, "hora_inicio": "08:00", "hora_fin": "14:00"}],
    }
    r = cliente.post("/tutores", json=carlos)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "AUL-T06" and r.json()["materias"] == ["química"]
    assert r.json()["correo"] == "carlos@correo.com"
    assert cliente.post("/tutores", json=carlos).status_code == 409
    sin_horario = cliente.post("/tutores", json={**carlos, "correo": "otro@correo.com", "bloques": []})
    assert sin_horario.status_code == 422
    al_reves = {**carlos, "correo": "otro@correo.com",
                "bloques": [{"dia_semana": 3, "hora_inicio": "14:00", "hora_fin": "08:00"}]}
    assert cliente.post("/tutores", json=al_reves).status_code == 422
    assert cliente.post("/tutores/acceso", json={"correo": "CARLOS@correo.com"}).json()["id"] == "AUL-T06"
    assert cliente.post("/tutores/acceso", json={"correo": "nadie@correo.com"}).status_code == 404
    assert cliente.get("/tutores/AUL-T06").status_code == 200
    assert crear_sesion(cliente, materia="Química")["tutor_id"] == "AUL-T06"
