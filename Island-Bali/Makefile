VENV_PYTHON = ./venv/bin/python
VENV_PIP = ./venv/bin/pip
PYTHON = $(shell test -f $(VENV_PYTHON) && echo $(VENV_PYTHON) || echo python3)

.PHONY: help venv install run up down migrate makemigrations shell createsuperuser changepassword

help:
	@echo "Available commands:"
	@echo "  make run            - Run Django development server"
	@echo "  make venv           - Create virtual environment"
	@echo "  make install        - Install dependencies into venv"
	@echo "  make up             - Run containers via docker compose"
	@echo "  make down           - Stop containers via docker compose"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create database migrations"
	@echo "  make shell          - Open Django shell"
	@echo "  make createsuperuser - Create a new Django superuser"
	@echo "  make changepassword - Change password for existing user"
	@echo "  make docker-createsuperuser - Create a new Django superuser inside Docker"
	@echo "  make docker-shell   - Open Django shell inside Docker"
	@echo "  make docker-seed-data - Seed database with mock cities, points, and products inside Docker"



venv:
	@if [ ! -d "venv" ]; then python3 -m venv venv; fi

install: venv
	$(VENV_PIP) install -r requirements.txt

run: venv
	$(PYTHON) manage.py runserver 0.0.0.0:8000

up:
	docker compose up -d

down:
	docker compose down

migrate: venv
	$(PYTHON) manage.py migrate

makemigrations: venv
	$(PYTHON) manage.py makemigrations

shell: venv
	$(PYTHON) manage.py shell

createsuperuser: venv
	$(PYTHON) manage.py createsuperuser

changepassword: venv
	$(PYTHON) manage.py changepassword admin

docker-createsuperuser:
	docker compose exec -it web python manage.py createsuperuser

docker-shell:
	docker compose exec -it web python manage.py shell

docker-seed-data:
	docker compose exec -it web python manage.py seed_data


