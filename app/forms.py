import re

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileSize
from wtforms import (
    StringField,
    PasswordField,
    SelectField,
    HiddenField,
    SubmitField,
    BooleanField,
)
from wtforms.validators import (
    DataRequired,
    Length,
    Email,
    Regexp,
    EqualTo,
    Optional,
    ValidationError,
)

PHONE_REGEX = r"^[0-9()+\-\s]{8,20}$"
USERNAME_REGEX = r"^[A-Za-z0-9_.\-]{3,80}$"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
_NON_DIGITS_RE = re.compile(r"\D+")


def no_control_chars(_form, field):
    """Bloqueia caracteres de controle (defesa extra contra payloads maliciosos
    em campos de texto, além do auto-escape padrão do Jinja2)."""
    value = field.data or ""
    if any(ord(ch) < 32 and ch not in ("\t",) for ch in value):
        raise ValidationError("Caractere inválido detectado no campo.")


class LoginForm(FlaskForm):
    username = StringField("Usuário", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("Senha", validators=[DataRequired(), Length(min=1, max=128)])
    submit = SubmitField("Entrar")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Senha atual", validators=[DataRequired()])
    new_password = PasswordField(
        "Nova senha",
        validators=[
            DataRequired(),
            Length(min=8, max=128, message="A senha deve ter ao menos 8 caracteres."),
            Regexp(r"^(?=.*[A-Za-z])(?=.*\d).+$", message="A senha deve conter letras e números."),
        ],
    )
    confirm_password = PasswordField(
        "Confirme a nova senha",
        validators=[DataRequired(), EqualTo("new_password", message="As senhas não coincidem.")],
    )
    submit = SubmitField("Alterar senha")


class UserCreateForm(FlaskForm):
    name = StringField(
        "Nome completo", validators=[DataRequired(), Length(min=2, max=120), no_control_chars]
    )
    username = StringField(
        "Usuário",
        validators=[
            DataRequired(),
            Length(min=3, max=80),
            Regexp(USERNAME_REGEX, message="Use apenas letras, números, ponto, hífen ou underscore."),
            no_control_chars,
        ],
    )
    role = SelectField(
        "Perfil",
        choices=[("user", "Usuário padrão"), ("supervisor", "Supervisor"), ("admin", "Administrador")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Criar usuário")

    def validate_username(self, field):
        """Para o perfil "Usuário padrão", o login passa a ser o CPF (só
        números) — aceita o CPF digitado com ou sem pontuação, mas normaliza
        para dígitos antes de salvar (é isso que vira username e senha
        inicial da conta). Perfis Supervisor/Administrador continuam com o
        cadastro de usuário livre de sempre, sem nenhuma mudança."""
        if self.role.data != "user":
            return
        digits = _NON_DIGITS_RE.sub("", field.data or "")
        if len(digits) != 11:
            raise ValidationError(
                'Para o perfil "Usuário padrão", o campo Usuário deve ser o CPF com 11 dígitos (somente números).'
            )
        field.data = digits


class UserEditForm(FlaskForm):
    name = StringField(
        "Nome completo", validators=[DataRequired(), Length(min=2, max=120), no_control_chars]
    )
    role = SelectField(
        "Perfil",
        choices=[("user", "Usuário padrão"), ("supervisor", "Supervisor"), ("admin", "Administrador")],
        validators=[DataRequired()],
    )
    is_active = SelectField(
        "Situação",
        choices=[("1", "Ativo"), ("0", "Inativo")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Salvar alterações")


class TemplateForm(FlaskForm):
    name = StringField(
        "Nome do modelo", validators=[DataRequired(), Length(min=2, max=120), no_control_chars]
    )
    variant = SelectField(
        "Variante do padrão",
        choices=[("sem_foto", "Sem foto"), ("com_foto", "Com foto")],
        default="sem_foto",
        validators=[DataRequired()],
    )
    background_image = FileField(
        "Imagem de fundo (PNG ou JPG)",
        validators=[
            Optional(),
            FileAllowed(["png", "jpg", "jpeg"], "Envie apenas arquivos PNG ou JPG."),
            FileSize(max_size=MAX_IMAGE_BYTES, message="A imagem deve ter no máximo 5MB."),
        ],
    )
    # Sem DataRequired de propósito: se o JavaScript do editor visual não
    # rodar por qualquer motivo no navegador do admin (bloqueio de extensão,
    # antivírus, JS desabilitado etc.), o modelo ainda deve poder ser salvo —
    # o servidor aplica um layout padrão razoável (ver validate_fields_json).
    fields_json = HiddenField("Configuração dos campos", validators=[Optional()])
    submit = SubmitField("Salvar modelo")


class SignatureForm(FlaskForm):
    full_name = StringField(
        "Nome completo",
        validators=[
            DataRequired(message="Informe o nome completo."),
            Length(min=2, max=80, message="O nome deve ter entre 2 e 80 caracteres."),
            no_control_chars,
        ],
    )
    role_title = StringField(
        "Função",
        validators=[
            DataRequired(message="Informe a função."),
            Length(min=2, max=60, message="A função deve ter entre 2 e 60 caracteres."),
            no_control_chars,
        ],
    )
    signature_email = StringField(
        "E-mail",
        validators=[
            DataRequired(message="Informe o e-mail."),
            Email(message="E-mail inválido."),
            Length(max=190),
        ],
    )
    phone = StringField(
        "Telefone",
        validators=[
            DataRequired(message="Informe o telefone."),
            Regexp(PHONE_REGEX, message="Telefone inválido. Use apenas números, espaços, parênteses, + e -."),
        ],
    )
    whatsapp = StringField(
        "WhatsApp (opcional)",
        validators=[
            Optional(),
            Regexp(PHONE_REGEX, message="WhatsApp inválido. Use apenas números, espaços, parênteses, + e -."),
        ],
    )
    unit = StringField(
        "Unidade / Gerência",
        validators=[
            DataRequired(message="Informe a unidade / gerência."),
            Length(min=2, max=45, message="A unidade / gerência deve ter entre 2 e 45 caracteres."),
            no_control_chars,
        ],
    )
    with_icons = BooleanField("Incluir ícones antes do e-mail, telefone e WhatsApp", default=False)
    with_photo = BooleanField("Gerar assinatura com foto", default=False)
    photo = FileField(
        "Foto do colaborador",
        validators=[
            Optional(),
            FileAllowed(["png", "jpg", "jpeg"], "Envie apenas arquivos PNG ou JPG."),
            FileSize(max_size=MAX_IMAGE_BYTES, message="A imagem deve ter no máximo 5MB."),
        ],
    )
    output_format = SelectField(
        "Formato de saída",
        choices=[("png", "PNG (recomendado)"), ("jpg", "JPG")],
        default="png",
        validators=[DataRequired()],
    )
    confirmed = HiddenField(default="0")
    submit = SubmitField("Gerar assinatura")


class BatchImportForm(FlaskForm):
    """Importação de planilha (admin/supervisor): gera assinaturas SEM FOTO em lote."""

    spreadsheet = FileField(
        "Planilha de colaboradores (.xlsx ou .csv)",
        validators=[
            DataRequired(message="Envie a planilha."),
            FileAllowed(["xlsx", "csv"], "Envie um arquivo .xlsx ou .csv."),
            FileSize(max_size=2 * 1024 * 1024, message="A planilha deve ter no máximo 2MB."),
        ],
    )
    output_format = SelectField(
        "Formato de saída",
        choices=[("png", "PNG (recomendado)"), ("jpg", "JPG")],
        default="png",
        validators=[DataRequired()],
    )
    with_icons = BooleanField(
        "Incluir ícones e número de WhatsApp (aplica a todo o lote)",
        default=False,
    )
    # Posições/estilos opcionais definidos na pré-visualização (arrastar os
    # campos sobre um exemplo antes de importar). Se vazio, usa a posição
    # salva no modelo ativo — nunca bloqueia o envio da planilha.
    fields_json = HiddenField("Posicionamento dos campos", validators=[Optional()])
    submit = SubmitField("Importar e gerar assinaturas")


class CpfImportForm(FlaskForm):
    """Importação em lote de CPFs: cria uma conta de Usuário padrão para cada
    linha (Nome + CPF) — login e senha iniciais são o próprio CPF (só
    números). Diferente de BatchImportForm: aqui o resultado é uma CONTA DE
    ACESSO ao sistema, não uma imagem de assinatura."""

    spreadsheet = FileField(
        "Planilha de CPFs (.xlsx ou .csv)",
        validators=[
            DataRequired(message="Envie a planilha."),
            FileAllowed(["xlsx", "csv"], "Envie um arquivo .xlsx ou .csv."),
            FileSize(max_size=2 * 1024 * 1024, message="A planilha deve ter no máximo 2MB."),
        ],
    )
    submit = SubmitField("Importar CPFs")
