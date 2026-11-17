from django.contrib import admin

from .models import (
    Assunto, Card, Certificado, Fonte, FonteCard, GuiaRapido, Opcao, Pergunta, ProgressoCard, ProgressoTrilha,
    TentativaPergunta, TentativaQuiz, Trilha,
)


class SemExclusaoMixin:
    def has_delete_permission(self, request, obj=None):
        return False


class AssuntoInline(SemExclusaoMixin, admin.TabularInline):
    model = Assunto
    extra = 0


class OpcaoInline(SemExclusaoMixin, admin.TabularInline):
    model = Opcao
    extra = 0


class FonteCardInline(admin.TabularInline):
    model = FonteCard
    extra = 0


@admin.register(Trilha)
class TrilhaAdmin(SemExclusaoMixin, admin.ModelAdmin):
    list_display = ('nome', 'carga_horaria_minutos', 'ativa')
    inlines = [AssuntoInline]


@admin.register(Assunto)
class AssuntoAdmin(SemExclusaoMixin, admin.ModelAdmin):
    list_display = ('titulo', 'ordem', 'ativo', 'excluido_em')


@admin.register(Card)
class CardAdmin(SemExclusaoMixin, admin.ModelAdmin):
    list_display = ('codigo', 'tema', 'assunto', 'ativo', 'excluido_em')
    list_filter = ('assunto',)
    search_fields = ('tema', 'explicacao')
    inlines = [FonteCardInline]


@admin.register(GuiaRapido)
class GuiaRapidoAdmin(SemExclusaoMixin, admin.ModelAdmin):
    list_display = ('titulo', 'ordem', 'ativo', 'excluido_em')


@admin.register(Pergunta)
class PerguntaAdmin(SemExclusaoMixin, admin.ModelAdmin):
    list_display = ('codigo', 'enunciado', 'ativo', 'excluido_em')
    inlines = [OpcaoInline]


@admin.register(TentativaQuiz)
class TentativaQuizAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'acertos', 'total_perguntas', 'percentual', 'aprovada', 'criado_em', 'finalizada_em')
    list_filter = ('aprovada',)


admin.site.register([Fonte, ProgressoCard, ProgressoTrilha, Certificado, TentativaPergunta])
