from django.contrib import admin

from .models import Assunto, Card, Certificado, Fonte, GuiaRapido, Opcao, Pergunta, ProgressoCard, TentativaQuiz, Trilha


class AssuntoInline(admin.TabularInline):
    model = Assunto
    extra = 0


class OpcaoInline(admin.TabularInline):
    model = Opcao
    extra = 0


@admin.register(Trilha)
class TrilhaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'carga_horaria_minutos', 'nota_minima_percentual', 'ativa')
    inlines = [AssuntoInline]


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'tema', 'assunto')
    list_filter = ('assunto',)
    search_fields = ('tema', 'explicacao')
    filter_horizontal = ('fontes',)


@admin.register(Pergunta)
class PerguntaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'enunciado', 'assunto')
    inlines = [OpcaoInline]


@admin.register(TentativaQuiz)
class TentativaQuizAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acertos', 'total', 'percentual', 'aprovada', 'criado_em')
    list_filter = ('aprovada',)


admin.site.register([Fonte, GuiaRapido, ProgressoCard, Certificado])
