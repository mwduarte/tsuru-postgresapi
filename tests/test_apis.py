# -*- coding: utf-8 -*-

try:
    import simplejson as json
except ImportError:
    import json

from postgresapi import models
from . import _base


class ApisTestCase(_base.TestCase):

    def setUp(self):
        super(ApisTestCase, self).setUp()
        self._drop_test_db()
        self._drop_test_user()
        self.client = self.app.test_client()

    def tearDown(self):
        super(ApisTestCase, self).tearDown()
        self._drop_test_db()
        self._drop_test_user()

    def test_create_201(self):
        rv = self.client.post('/resources', data={
            'name': 'databasenotexist'
        })
        self.assertEqual(rv.status_code, 201)

    def test_create_400(self):
        rv = self.client.post('/resources')
        self.assertEqual(rv.status_code, 400)
        rv = self.client.post('/resources', data={
            'name': ''
        })
        self.assertEqual(rv.status_code, 400)

    def test_create_500(self):
        with self.app.app_context():
            models.Instance.create('databasenotexist')
        rv = self.client.post('/resources', data={
            'name': 'databasenotexist'
        })
        self.assertEqual(rv.status_code, 500)
        self.assertTrue('already exists' in rv.data)

    def test_bind_app_201(self):
        with self.app.app_context():
            models.Instance.create('databasenotexist')
        rv = self.client.post('/resources/databasenotexist', data={
            'hostname': 'testapp.example.com'
        })
        self.assertEqual(rv.status_code, 201)
        self.assertEqual(json.loads(rv.data), {
            'PG_DATABASE': 'databasenotexist',
            'PG_HOST': 'db.example.com',
            'PG_PASSWORD': '12e7935efbd56116a0121c26582c00f108aeebd2',
            'PG_PORT': 5432,
            'PG_USER': 'databasenofdbf8d'
        })

    def test_bind_app_400(self):
        rv = self.client.post('/resources/databasenotexist')
        self.assertEqual(rv.status_code, 400)
        rv = self.client.post('/resources/databasenotexist', data={
            'hostname': ''
        })
        self.assertEqual(rv.status_code, 400)

    def test_bind_app_404(self):
        rv = self.client.post('/resources/databasenotexist', data={
            'hostname': 'testapp.example.com'
        })
        self.assertEqual(rv.status_code, 404)

    def test_bind_app_412(self):
        with self.app.app_context():
            models.Instance.create('databasenotexist')
        db = self.create_db()
        with db.transaction() as cursor:
            cursor.execute("UPDATE instance SET state='pending'")
        rv = self.client.post('/resources/databasenotexist', data={
            'hostname': 'testapp.example.com'
        })
        self.assertEqual(rv.status_code, 412)

    def test_bind_app_500(self):
        with self.app.app_context():
            ins = models.Instance.create('databasenotexist')
            ins.create_user('testapp.example.com')
        rv = self.client.post('/resources/databasenotexist', data={
            'hostname': 'testapp.example.com'
        })
        self.assertEqual(rv.status_code, 500)
        self.assertEqual(rv.data.strip(),
                         'role "databasenofdbf8d" already exists')

    def test_unbind_app_200(self):
        with self.app.app_context():
            ins = models.Instance.create('databasenotexist')
            ins.create_user('testapp.example.com')
        rv = self.client.delete('/resources/databasenotexist'
                                '/hostname/testapp.example.com')
        self.assertEqual(rv.status_code, 200)

    def test_unbind_app_404(self):
        rv = self.client.delete('/resources/databasenotexist'
                                '/hostname/testapp.example.com')
        self.assertEqual(rv.status_code, 404)

    def test_unbind_app_500(self):
        with self.app.app_context():
            models.Instance.create('databasenotexist')
        # the database exists but not the role
        # tsuru's api flow set this to 500 but not 404
        rv = self.client.delete('/resources/databasenotexist'
                                '/hostname/testapp.example.com')
        self.assertEqual(rv.status_code, 500)

        db = self.create_db()
        with db.transaction() as cursor:
            cursor.execute("UPDATE instance SET state='pending'")
        rv = self.client.delete('/resources/databasenotexist'
                                '/hostname/testapp.example.com')
        self.assertEqual(rv.status_code, 500)

    def test_destroy_200(self):
        with self.app.app_context():
            models.Instance.create('databasenotexist')
        rv = self.client.delete('/resources/databasenotexist')
        self.assertEqual(rv.status_code, 200)

    def test_destroy_404(self):
        rv = self.client.delete('/resources/databasenotexist')
        self.assertEqual(rv.status_code, 404)

    def test_status(self):
        rv = self.client.get('/resources/databasenotexist/status')
        self.assertEqual(rv.status_code, 404)

        with self.app.app_context():
            models.Instance.create('databasenotexist')
        rv = self.client.get('/resources/databasenotexist/status')
        self.assertEqual(rv.status_code, 204)

        password = self.app.config['SHARED_ADMIN_PASSWORD']
        self.app.config['SHARED_ADMIN_PASSWORD'] = password * 2
        rv = self.client.get('/resources/databasenotexist/status')
        self.assertEqual(rv.status_code, 500)

        self.app.config['SHARED_ADMIN_PASSWORD'] = password
        db = self.create_db()
        with db.transaction() as cursor:
            cursor.execute("UPDATE instance SET state='pending'")
        rv = self.client.get('/resources/databasenotexist/status')
        self.assertEqual(rv.status_code, 202)

        with db.transaction() as cursor:
            cursor.execute("UPDATE instance SET state='error'")
        rv = self.client.get('/resources/databasenotexist/status')
        self.assertEqual(rv.status_code, 500)