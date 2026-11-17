FLUXOS = (
    ('sem_fluxo', 'Não'),
    ('leve', 'Leve'),
    ('medio', 'Médio'),
    ('intenso', 'Intenso'),
)

HUMORES = (
    ('triste', 'Triste'),
    ('cansada', 'Cansada'),
    ('normal', 'Normal'),
    ('animada', 'Animada'),
)

INTENSIDADES = (
    ('nenhum', 'Nenhum'),
    ('leve', 'Leve'),
    ('medio', 'Médio'),
    ('intenso', 'Intenso'),
)

SITUACOES_MENSTRUAIS = (
    ('ja_menstruo', 'Já menstruo'),
    ('ainda_nao', 'Ainda não'),
    ('nao_tenho_certeza', 'Não tenho certeza'),
)

FLUXOS_COM_MENSTRUACAO = ('leve', 'medio', 'intenso')
INTENSIDADES_GRAVADAS = ('leve', 'medio', 'intenso')
SITUACOES_COM_DIARIO = ('ja_menstruo', 'nao_tenho_certeza')

SINTOMAS_INICIAIS = (
    ('colica', 'Cólica'),
    ('dor_de_cabeca', 'Dor de cabeça'),
    ('dor_nas_costas', 'Dor nas costas'),
    ('inchaco', 'Inchaço'),
    ('sensibilidade_seios', 'Sensibilidade nos seios'),
    ('acne', 'Acne'),
    ('nausea', 'Náusea'),
    ('apetite', 'Mudança no apetite'),
)

CICLO_MINIMO_DIAS = 21
CICLO_MAXIMO_DIAS = 45
JANELA_INICIO_DIAS = 7
CICLOS_NA_MEDIA = 6
CICLOS_VALIDOS_MINIMOS = 2
REGISTROS_MINIMOS_TENDENCIA = 3
SINTOMAS_NA_TENDENCIA = 3

AVISO_RESUMO = (
    'Esta é uma estimativa baseada nos seus registros e pode mudar. '
    'Não substitui avaliação médica e não é método contraceptivo.'
)
ORIENTACAO_CICLOS_DESCARTADOS = 'Alguns ciclos ficaram fora da faixa esperada. Vale conversar com um profissional de saúde.'

MENSAGEM_CONSENTIMENTO_SAUDE = 'Para usar o diário do corpo, aceite o consentimento de dados de saúde no seu perfil.'
MENSAGEM_DIARIO_INDISPONIVEL = 'O diário do corpo aparece quando você conta no perfil que já menstrua ou que não tem certeza.'
MENSAGEM_PERFIL_ADMIN = 'O diário do corpo é pessoal e não fica disponível para o perfil admin.'


def rotulos(opcoes):
    return [{'codigo': codigo, 'rotulo': rotulo} for codigo, rotulo in opcoes]


def codigos(opcoes):
    return tuple(codigo for codigo, _ in opcoes)
