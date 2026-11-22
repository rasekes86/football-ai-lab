import unittest
from datetime import datetime, timezone
from football_ai_lab.verify_results import make_summary, keep_verified, OUTPUTS

NOW = datetime(2026, 11, 22, 21, 0, tzinfo=timezone.utc)

def selection(result="1", state="FINALIZADO", key="a"):
    return {"id":"SP1|match", "clave":key, "liga":"LaLiga",
            "local":"Equipo A","visitante":"Equipo B",
            "fecha_utc":"2026-11-22T15:00:00Z",
            "archivado_utc":"2026-11-21T15:00:00Z",
            "estado":state,"resultado":result,
            "seleccion":"Más de 1,5 goles","mercado":"goals",
            "cuota_decimal":"1.8",
            "tipo_cuota":"OFRECIDA_API_REGISTRADA"}

class ManualVerificationTests(unittest.TestCase):
    def test_no_data_never_counts_as_loss(self):
        result=make_summary([selection(result="",state="RESULTADO_NO_DISPONIBLE")],
                            [],[],[],NOW)
        self.assertEqual(result["top3"]["fallos"],0)
        self.assertEqual(result["top3"]["pendientes"],1)

    def test_overlapping_additional_replaces_one_top_market(self):
        result=make_summary([selection()],[selection()],[],[],NOW)
        self.assertEqual(result["top3"]["registradas"],0)
        self.assertEqual(result["adicional"]["aciertos"],1)
        self.assertEqual(result["nuevas_liquidaciones"],1)

    def test_additional_must_be_over_150(self):
        extra=selection()
        extra["cuota_decimal"]="1.50"
        result=make_summary([],[extra],[],[],NOW)
        self.assertEqual(result["adicional"]["registradas"],0)

    def test_repeat_is_idempotent(self):
        row=selection()
        report=make_summary([row],[],[row],[],NOW)
        self.assertEqual(report["nuevas_liquidaciones"],0)

    def test_keep_verified_when_data_source_is_missing(self):
        old=selection()
        missing=selection(result="",state="ESTADISTICA_NO_DISPONIBLE")
        self.assertEqual(keep_verified([missing],[old],"clave"),[old])

    def test_no_archived_file_is_in_write_allowlist(self):
        self.assertTrue(all(not name.startswith("historico_") for name in OUTPUTS))

if __name__=="__main__":
    unittest.main()
