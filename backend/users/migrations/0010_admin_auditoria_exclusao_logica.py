import os

import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


def _triggers_ativos(schema_editor):
    return (
        schema_editor.connection.vendor == 'mysql'
        and os.getenv('DB_TRIGGERS', 'True') == 'True'
    )


class RunSQLSomenteMySQL(migrations.RunSQL):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if _triggers_ativos(schema_editor):
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if _triggers_ativos(schema_editor):
            super().database_backwards(app_label, schema_editor, from_state, to_state)


TRIGGER_ADMIN = """
CREATE TRIGGER users_bloqueia_exclusao_admin
BEFORE DELETE ON users
FOR EACH ROW
BEGIN
    IF OLD.perfil = 'admin' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Conta admin nao pode ser excluida.';
    END IF;
END
"""

TRIGGER_LOGS = """
CREATE TRIGGER logs_atividade_bloqueia_exclusao
BEFORE DELETE ON logs_atividade
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Logs de atividade nao podem ser apagados.';
END
"""


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_email_colacao_binaria'),
    ]

    operations = [
        migrations.CreateModel(
            name='TentativaLogin',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('contato_hash', models.CharField(db_index=True, max_length=64)),
                ('ip_origem', models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'db_table': 'tentativas_login',
            },
        ),
        migrations.CreateModel(
            name='TrocaEmailPendente',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('email_novo', models.EmailField(max_length=150)),
                ('codigo_hash', models.CharField(max_length=255)),
                ('tentativas', models.PositiveSmallIntegerField(default=0)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('expira_em', models.DateTimeField()),
            ],
            options={
                'db_table': 'trocas_email_pendentes',
            },
        ),
        migrations.AddField(
            model_name='logatividade',
            name='alvo_id',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='logatividade',
            name='alvo_tipo',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
        migrations.AddField(
            model_name='logatividade',
            name='ator',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='logs_como_ator', to='users.usuario'),
        ),
        migrations.AddField(
            model_name='logatividade',
            name='resumo',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='usuario',
            name='ativo',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='demo',
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name='usuario',
            name='excluido_em',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='usuario',
            name='perfil',
            field=models.CharField(choices=[('user', 'User'), ('admin', 'Admin')], default='user', max_length=10),
        ),
        migrations.AlterField(
            model_name='logatividade',
            name='acao',
            field=models.CharField(choices=[('cadastro', 'Cadastro realizado'), ('login_sucesso', 'Login com sucesso'), ('login_falha', 'Tentativa de login falhou'), ('login_bloqueado', 'Login bloqueado temporariamente'), ('redefinicao_senha_solicitada', 'Redefinição de senha solicitada'), ('senha_redefinida', 'Senha redefinida'), ('codigo_2fa_enviado', 'Código de verificação enviado'), ('codigo_2fa_invalido', 'Código de verificação inválido'), ('login_google', 'Login com Google'), ('logout', 'Saiu da conta'), ('perfil_atualizado', 'Perfil atualizado'), ('consentimento_revogado', 'Consentimento revogado'), ('consentimento_reativado', 'Consentimento reativado'), ('exportacao_dados', 'Exportação dos dados'), ('exclusao_conta_propria', 'Conta excluída pela própria pessoa'), ('exclusao_conta_recusada', 'Exclusão de conta recusada'), ('exclusao_conta_demo', 'Conta de demonstração removida'), ('email_alteracao_solicitada', 'Troca de email solicitada'), ('email_alteracao_recusada', 'Troca de email recusada'), ('email_alteracao_codigo_invalido', 'Código de troca de email inválido'), ('email_alteracao_expirada', 'Troca de email expirada'), ('email_alterado', 'Email alterado'), ('email_alterado_aviso_falhou', 'Aviso de troca de email não enviado'), ('exclusao_aviso_falhou', 'Aviso de exclusão de conta não enviado'), ('admin_criado', 'Admin criado ou promovido'), ('admin_login', 'Login de admin'), ('admin_consultou_dashboard', 'Admin consultou o dashboard'), ('admin_consultou_logs', 'Admin consultou os logs'), ('admin_listou_usuarios', 'Admin listou users'), ('admin_excluiu_usuario', 'Admin excluiu user'), ('admin_criou_conteudo', 'Admin criou conteúdo'), ('admin_editou_conteudo', 'Admin editou conteúdo'), ('admin_desativou_conteudo', 'Admin desativou conteúdo'), ('admin_acesso_negado', 'Acesso admin negado')], max_length=40),
        ),
        migrations.AlterField(
            model_name='logatividade',
            name='criado_em',
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
        migrations.AddIndex(
            model_name='logatividade',
            index=models.Index(fields=['acao', '-criado_em'], name='logs_ativid_acao_09c440_idx'),
        ),
        migrations.AddField(
            model_name='trocaemailpendente',
            name='usuario',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='troca_email_pendente', to='users.usuario'),
        ),
        RunSQLSomenteMySQL(
            sql=[TRIGGER_ADMIN], reverse_sql=['DROP TRIGGER IF EXISTS users_bloqueia_exclusao_admin'],
        ),
        RunSQLSomenteMySQL(
            sql=[TRIGGER_LOGS], reverse_sql=['DROP TRIGGER IF EXISTS logs_atividade_bloqueia_exclusao'],
        ),
    ]
