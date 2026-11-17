from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0010_admin_auditoria_exclusao_logica'),
    ]

    operations = [
        migrations.AlterField(
            model_name='logatividade',
            name='acao',
            field=models.CharField(choices=[('cadastro', 'Cadastro realizado'), ('login_sucesso', 'Login com sucesso'), ('login_falha', 'Tentativa de login falhou'), ('login_bloqueado', 'Login bloqueado temporariamente'), ('redefinicao_senha_solicitada', 'Redefinição de senha solicitada'), ('senha_redefinida', 'Senha redefinida'), ('codigo_2fa_enviado', 'Código de verificação enviado'), ('codigo_2fa_invalido', 'Código de verificação inválido'), ('login_google', 'Login com Google'), ('logout', 'Saiu da conta'), ('perfil_atualizado', 'Perfil atualizado'), ('consentimento_revogado', 'Consentimento revogado'), ('consentimento_reativado', 'Consentimento reativado'), ('exportacao_dados', 'Exportação dos dados'), ('exclusao_conta_propria', 'Conta excluída pela própria pessoa'), ('exclusao_conta_recusada', 'Exclusão de conta recusada'), ('exclusao_conta_demo', 'Conta de demonstração removida'), ('email_alteracao_solicitada', 'Troca de email solicitada'), ('email_alteracao_recusada', 'Troca de email recusada'), ('email_alteracao_codigo_invalido', 'Código de troca de email inválido'), ('email_alteracao_expirada', 'Troca de email expirada'), ('email_alterado', 'Email alterado'), ('email_alterado_aviso_falhou', 'Aviso de troca de email não enviado'), ('exclusao_aviso_falhou', 'Aviso de exclusão de conta não enviado'), ('documentos_aceitos', 'Novas versões dos documentos aceitas'), ('admin_criado', 'Admin criado ou promovido'), ('admin_login', 'Login de admin'), ('admin_consultou_dashboard', 'Admin consultou o dashboard'), ('admin_consultou_logs', 'Admin consultou os logs'), ('admin_listou_usuarios', 'Admin listou users'), ('admin_excluiu_usuario', 'Admin excluiu user'), ('admin_criou_conteudo', 'Admin criou conteúdo'), ('admin_editou_conteudo', 'Admin editou conteúdo'), ('admin_desativou_conteudo', 'Admin desativou conteúdo'), ('admin_acesso_negado', 'Acesso admin negado')], max_length=40),
        ),
    ]
