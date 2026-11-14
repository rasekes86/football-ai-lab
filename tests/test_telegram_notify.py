import io,json,unittest
from urllib.request import Request
from football_ai_lab.telegram_notify import message,send

class TelegramTests(unittest.TestCase):
    def test_message_no_fake_prices(self):
        data={"calculado_utc":"2026-11-14T20:00:00Z",
              "top_3_jornada":[{"local":"Real Madrid","visitante":"Celta",
                    "seleccion":"Más de 1,5 goles","probabilidad":.8,"cuota_justa":1.25}]}
        txt=message(data,{"registradas":3,"finalizadas":0})
        self.assertIn("cuota justa, NO ofrecida",txt)
        self.assertIn("Real Madrid",txt)
        self.assertIn("finalizados y verificados: 0",txt)
    def test_http_post_with_dummy_credentials(self):
        received=[]
        class Reply:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self):return b'{"ok":true}'
        def opening(req,timeout):
            received.append(req)
            self.assertEqual(timeout,10)
            return Reply()
        self.assertTrue(send("Hello","12345:ABCDEFghijkLMnopQrstuv_000",
                            "-1234567890",opener=opening))
        self.assertEqual(json.loads(received[0].data)["text"],"Hello")
        self.assertEqual(received[0].get_method(),"POST")
    def test_bad_token_rejected(self):
        with self.assertRaises(ValueError):send("test","not-a-bot-token","12345678")
if __name__=="__main__":unittest.main()
