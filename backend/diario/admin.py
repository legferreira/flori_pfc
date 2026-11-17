from django.contrib import admin

from .models import Sintoma


@admin.register(Sintoma)
class SintomaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome', 'ativo', 'ordem')

    def has_delete_permission(self, request, obj=None):
        return False
