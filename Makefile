all:

test:
	DJANGO_SETTINGS_MODULE=contractor.settings py.test-3 -x --cov=contractor/tscript --cov-report html --cov-report term -vv contractor/tscript


make_test_db:
	if [ -e db.sqlite3 ] ; then echo "DB Allready exists"; exit 1 ; fi
	cd local/api_server && ./manage.py migrate && ./load_test_data


start_api_server:
	cd local/api_server && ./api_server.py