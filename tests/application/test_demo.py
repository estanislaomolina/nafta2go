"""La demo recorre la conexión completa usando exclusivamente datos ficticios."""

import pytest

from nafta2go.demo import main


def test_default_demo_explains_computed_results_and_missing_route(capsys):
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "DEMOSTRACIÓN SINTÉTICA" in output
    assert "sin ranking" in output
    assert "demo-a" in output and "demo-b" in output
    assert "Compra estimada: 10.00 L por $12000.00" in output
    assert "Combustible al finalizar: 17.00 L" in output
    assert "Combustible al finalizar: 15.00 L" in output
    assert "Desvío: 5.00 km; tiempo adicional: 10.00 min" in output
    assert "No se obtuvo una ruta completa" in output


def test_demo_round_trip_uses_full_trip_as_detour(capsys):
    assert main(["--sin-destino"]) == 0
    output = capsys.readouterr().out
    assert "ida y vuelta al origen" in output
    assert "Desvío: 30.00 km; tiempo adicional: 40.00 min" in output


def test_demo_budget_changes_purchase(capsys):
    assert main(["--presupuesto", "6000"]) == 0
    output = capsys.readouterr().out
    assert "Compra estimada: 5.00 L por $6000.00" in output
    assert "Combustible al finalizar: 12.00 L" in output


def test_demo_with_no_reachable_station_reports_failure(capsys):
    assert main(["--litros-iniciales", "0"]) == 1
    output = capsys.readouterr().out
    assert "El combustible no alcanza para llegar" in output
    assert "Ninguna alternativa viable" in output
    assert "Compra estimada" not in output


@pytest.mark.parametrize(
    "args,flag",
    [
        (["--presupuesto", "-1"], "--presupuesto"),
        (["--consumo", "0"], "--consumo"),
        (["--reserva", "51"], "--reserva"),
        (["--capacidad", "NaN"], "--capacidad"),
        (["--presupuesto", "abc"], "--presupuesto"),
    ],
)
def test_invalid_query_is_actionable(args, flag, capsys):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    assert flag in capsys.readouterr().err
