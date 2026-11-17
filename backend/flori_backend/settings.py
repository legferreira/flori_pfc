import os

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
load_dotenv()


def _lista(nome, padrao=''):
    return [item.strip() for item in os.getenv(nome, padrao).split(',') if item.strip()]


def _inteiro(nome, padrao):
    try:
        return int(os.getenv(nome, '') or padrao)
    except ValueError:
        raise ImproperlyConfigured(f'{nome} precisa ser um número inteiro.')


DEBUG = os.getenv('DEBUG', 'False') == 'True'

SECRET_KEY = os.getenv('SECRET_KEY', '').strip()
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Defina SECRET_KEY no .env.')
    SECRET_KEY = 'django-insecure-somente-para-desenvolvimento-local'

ALLOWED_HOSTS = _lista('ALLOWED_HOSTS')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'users',
    'trilha',
    'administracao',
    'diario',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'flori_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'flori_backend.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TEST': {
            'CHARSET': 'utf8mb4',
        },
    }
}
BREVO_API_KEY = os.getenv('BREVO_API_KEY', '').strip()
BREVO_REMETENTE_EMAIL = os.getenv('BREVO_REMETENTE_EMAIL', '').strip()
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://127.0.0.1:5500').rstrip('/')
FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', 'flori-1742a').strip()

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = _lista('CORS_ALLOWED_ORIGINS', FRONTEND_URL)

CONFIA_EM_X_FORWARDED_FOR = os.getenv('CONFIA_EM_X_FORWARDED_FOR', 'False') == 'True'

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if CONFIA_EM_X_FORWARDED_FOR:
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

LOG_RETENCAO_DIAS = _inteiro('LOG_RETENCAO_DIAS', 365)
LOG_RETENCAO_ADMIN_DIAS = _inteiro('LOG_RETENCAO_ADMIN_DIAS', 1825)
CONSENTIMENTO_RETENCAO_DIAS = _inteiro('CONSENTIMENTO_RETENCAO_DIAS', 1825)


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
