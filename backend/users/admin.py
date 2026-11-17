from django.contrib import admin

from .models import LogAtividade, Usuario


class SomenteLeituraAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions


@admin.register(Usuario)
class UsuarioAdmin(SomenteLeituraAdmin):
    list_display = ('apelido', 'perfil', 'ativo', 'criado_em', 'excluido_em')
    list_filter = ('perfil', 'ativo')
    fields = ('id', 'apelido', 'perfil', 'ativo', 'criado_em', 'excluido_em')
    readonly_fields = fields


@admin.register(LogAtividade)
class LogAtividadeAdmin(SomenteLeituraAdmin):
    list_display = ('acao', 'usuario', 'ator', 'alvo_tipo', 'criado_em')
    list_filter = ('acao',)
    fields = ('acao', 'usuario', 'ator', 'alvo_tipo', 'alvo_id', 'resumo', 'ip_origem', 'criado_em')
    readonly_fields = fields

