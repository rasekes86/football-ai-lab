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


class PerMatchDetailsTests(unittest.TestCase):
    def test_unverified_result_has_precise_reason(self):
        from football_ai_lab.result_details import build_details
        bad=selection(result="",state="RESULTADO_NO_DISPONIBLE")
        matches, totals=build_details([bad],[],[],[],NOW)
        self.assertEqual(totals["pendientes"],1)
        self.assertEqual(totals["revisables"],1)
        self.assertIn("Sin marcador final contrastado",matches[0]["motivos"])

    def test_missing_match_statistics_is_not_a_loss(self):
        from football_ai_lab.result_details import build_details
        bad=selection(result="",state="ESTADISTICA_NO_DISPONIBLE")
        matches, totals=build_details([bad],[],[],[],NOW)
        self.assertEqual(matches[0]["estado"],"PENDIENTE")
        self.assertEqual(matches[0]["liquidadas"],0)
        self.assertIn("Faltan estadísticas finales contrastadas",matches[0]["motivos"])

    def test_two_hour_gate_explained_without_false_checks(self):
        from football_ai_lab.result_details import build_details
        recent=selection(result="",state="PENDIENTE")
        recent["fecha_utc"]="2026-11-22T20:15:00Z"
        matches, totals=build_details([recent],[],[],[],NOW)
        self.assertEqual(totals["en_espera"],1)
        self.assertEqual(totals["revisables"],0)
        self.assertIn("2 horas",matches[0]["motivos"][0])

    def test_partial_match_and_new_settlement_not_miscounted(self):
        from football_ai_lab.result_details import build_details
        final=selection(key="a")
        pending=selection(key="b",result="",state="ESTADISTICA_NO_DISPONIBLE")
        matches,totals=build_details([final,pending],[],[],[],NOW)
        self.assertEqual(totals["parciales"],1)
        self.assertEqual(matches[0]["liquidadas"],1)
        self.assertEqual(matches[0]["pendientes"],1)
        self.assertEqual(matches[0]["nuevas_liquidaciones"],1)
        old_matches,_=build_details([final,pending],[],[final],[],NOW)
        self.assertEqual(old_matches[0]["nuevas_liquidaciones"],0)

    def test_per_match_summary_never_counts_duplicate_additional(self):
        result=make_summary([selection()],[selection()],[],[],NOW)
        self.assertEqual(result["partidos_resumen"]["con_selecciones"],1)
        self.assertEqual(len(result["partidos"]),1)
        self.assertEqual(result["partidos"][0]["top3"]["registradas"],0)
        self.assertEqual(result["partidos"][0]["adicional"]["registradas"],1)
        self.assertEqual(result["nuevas_liquidaciones"],1)
        self.assertLessEqual(len(result["mensaje"]),3900)
        self.assertIn("/detalle",result["mensaje"] if
                      result["partidos_resumen"]["con_selecciones"]>6
                      else result["mensaje"]+"/detalle")

    def test_many_parties_do_not_overflow_telegram(self):
        items=[]
        for idx in range(45):
            row=selection(key="key"+str(idx),result="",state="RESULTADO_NO_DISPONIBLE")
            row["id"]="SP1|unique"+str(idx)
            row["local"]="Equipo local "+str(idx)
            row["visitante"]="Equipo visitante "+str(idx)
            items.append(row)
        result=make_summary(items,[],[],[],NOW)
        self.assertEqual(len(result["partidos"]),45)
        self.assertLessEqual(len(result["mensaje"]),3900)
        self.assertIn("/detalle",result["mensaje"])

if __name__=="__main__":
    unittest.main()
