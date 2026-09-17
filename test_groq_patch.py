"""Offline regression tests: no credentials, database, or outbound calls."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock
import unittest
import time
from threading import Lock
from flask import Flask, g, request, current_app, flash, get_flashed_messages
from openai import APIStatusError, APIConnectionError
import httpx
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).parent

class Tests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'offline-test'
        self.app.config.update(GROQ_API_KEY='fake', GROQ_MODEL='openai/gpt-oss-120b')
        tree = ast.parse((ROOT/'app/routes/ia.py').read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'asistente')
        function.decorator_list = []
        self.model = MagicMock()
        self.model.query.filter_by.return_value.order_by.return_value.limit.return_value.all.return_value = []
        self.client = MagicMock()
        self.api = self.client.return_value.__enter__.return_value.chat.completions.create
        self.api.return_value = NS(choices=[NS(message=NS(content='Una variable almacena un valor.'))], model='openai/gpt-oss-120b')
        self.db = MagicMock()
        self.env = dict(time=time, request=request, current_app=current_app, g=g, flash=flash,
            actividad_disponible=lambda _: NS(id=1,titulo='Prueba',descripcion='Ejercicio'),
            TIPOS_AYUDA={'explicacion':'Explicación'}, _consulta_lock=Lock(), _ultimas_consultas={},
            OpenAI=self.client, InteraccionIA=self.model, db=self.db, sesion_reciente=lambda _:None,
            redirect=lambda x:x, url_for=lambda *a,**kw:'/ok', render_template=lambda *a,**kw:kw,
            APIStatusError=APIStatusError, APIConnectionError=APIConnectionError,
            SQLAlchemyError=type('SQLAlchemyError',(Exception,),{}))
        exec(compile(ast.Module(body=[function],type_ignores=[]),'<route>','exec'),self.env)

    def call(self, data=None):
        with self.app.test_request_context('/',method='POST',data=data or {'consulta':'Qué es una variable','tipo_ayuda':'explicacion'}):
            g.usuario=NS(id=1)
            result=self.env['asistente'](1)
            return result,get_flashed_messages()

    def test_success(self):
        self.call()
        self.db.session.commit.assert_called_once()
        self.assertEqual(self.model.call_args.kwargs['proveedor'],'Groq')
        self.assertEqual(self.model.call_args.kwargs['modelo'],'openai/gpt-oss-120b')
        self.assertEqual(self.client.call_args.kwargs['max_retries'],0)

    def test_missing_key(self):
        self.app.config['GROQ_API_KEY']=''
        _,msg=self.call()
        self.assertIn('GROQ_API_KEY',msg[0]); self.client.assert_not_called()

    def test_invalid_input(self):
        self.call({'consulta':'','tipo_ayuda':'explicacion'})
        self.client.assert_not_called()

    def test_permission_and_quota_errors(self):
        for code in (401,403,404,429,500):
            self.env['_ultimas_consultas'].clear()
            self.api.side_effect=APIStatusError('secret-not-to-display',response=httpx.Response(code,request=httpx.Request('POST','https://api.groq.com')),body=None)
            _,msg=self.call()
            self.assertTrue(msg); self.assertNotIn('secret',str(msg))
            self.assertFalse(self.env['_consulta_lock'].locked())
        self.db.session.commit.assert_not_called()

    def test_connection_error(self):
        self.api.side_effect=APIConnectionError(request=httpx.Request('POST','https://api.groq.com'))
        _,msg=self.call(); self.assertIn('conectar',msg[0])

    def test_cooldown(self):
        self.call(); self.call(); self.api.assert_called_once()

    def test_busy(self):
        self.env['_consulta_lock'].acquire()
        _,msg=self.call(); self.client.assert_not_called(); self.assertIn('otra consulta',msg[0])

    def test_unauthorized_activity(self):
        self.env['actividad_disponible']=lambda _:None
        self.call(); self.client.assert_not_called()

    def test_templates(self):
        env=Environment(loader=FileSystemLoader(ROOT/'app/templates'))
        env.filters['markdown_seguro']=str
        env.filters['duracion_legible']=str
        for name in ('ia/asistente.html','ia/formulario.html','trabajo/actividad.html','ia/lista.html'):
            env.parse(env.loader.get_source(env,name)[0])
            env.get_template(name)
        text=(ROOT/'app/templates/ia/asistente.html').read_text(encoding='utf-8')
        self.assertIn('name="consulta"',text)
        self.assertNotIn('Respuesta de Gemini',text)

    def test_optional_manual_fields(self):
        tree=ast.parse((ROOT/'app/routes/ia.py').read_text(encoding='utf-8'))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validar_formulario')
        self.env.update(ESTADOS={'pendiente':'Pendiente'},SesionTrabajo=MagicMock())
        self.env['SesionTrabajo'].query.filter_by.return_value.order_by.return_value.first.return_value=None
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<validation>','exec'),self.env)
        with self.app.test_request_context('/',method='POST',data={'actividad_id':'1','consulta':'Prueba','tipo_ayuda':'explicacion','estado':'pendiente'}):
            g.usuario=NS(id=1)
            datos,errores=self.env['validar_formulario']([NS(id=1)])
            self.assertEqual(errores,[])
            self.assertIsNone(datos['modelo']); self.assertIsNone(datos['respuesta'])

if __name__=='__main__': unittest.main()
