import os
import resend


def send_password_reset_email(
    recipient_email: str,
    recipient_name: str,
    reset_url: str
) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    from_email = os.getenv("MAIL_FROM_EMAIL")
    from_name = os.getenv("MAIL_FROM_NAME", "SportFlow")

    if not api_key:
        raise RuntimeError("RESEND_API_KEY no está configurada")

    if not from_email:
        raise RuntimeError("MAIL_FROM_EMAIL no está configurado")

    resend.api_key = api_key

    safe_name = recipient_name or "usuario"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      </head>

      <body style="
        margin: 0;
        padding: 0;
        background-color: #f1f5f9;
        font-family: Arial, Helvetica, sans-serif;
        color: #0f172a;
      ">
        <table
          role="presentation"
          width="100%"
          cellspacing="0"
          cellpadding="0"
          style="background-color: #f1f5f9; padding: 32px 16px;"
        >
          <tr>
            <td align="center">
              <table
                role="presentation"
                width="100%"
                cellspacing="0"
                cellpadding="0"
                style="
                  max-width: 560px;
                  background-color: #ffffff;
                  border-radius: 18px;
                  overflow: hidden;
                  border: 1px solid #e2e8f0;
                "
              >
                <tr>
                  <td style="
                    height: 6px;
                    background-color: #1e3a8a;
                  "></td>
                </tr>

                <tr>
                  <td style="padding: 36px;">
                    <p style="
                      margin: 0 0 24px;
                      color: #1e3a8a;
                      font-size: 18px;
                      font-weight: 700;
                    ">
                      SportFlow
                    </p>

                    <h1 style="
                      margin: 0 0 16px;
                      font-size: 26px;
                      line-height: 1.2;
                      color: #0f172a;
                    ">
                      Restablece tu contraseña
                    </h1>

                    <p style="
                      margin: 0 0 16px;
                      color: #475569;
                      font-size: 15px;
                      line-height: 1.6;
                    ">
                      Hola {safe_name},
                    </p>

                    <p style="
                      margin: 0 0 26px;
                      color: #475569;
                      font-size: 15px;
                      line-height: 1.6;
                    ">
                      Recibimos una solicitud para cambiar la contraseña de tu
                      cuenta en SportFlow.
                    </p>

                    <table role="presentation" cellspacing="0" cellpadding="0">
                      <tr>
                        <td
                          align="center"
                          style="
                            border-radius: 10px;
                            background-color: #1e3a8a;
                          "
                        >
                          <a
                            href="{reset_url}"
                            style="
                              display: inline-block;
                              padding: 13px 22px;
                              color: #ffffff;
                              text-decoration: none;
                              font-size: 15px;
                              font-weight: 700;
                            "
                          >
                            Crear nueva contraseña
                          </a>
                        </td>
                      </tr>
                    </table>

                    <p style="
                      margin: 28px 0 0;
                      color: #64748b;
                      font-size: 13px;
                      line-height: 1.6;
                    ">
                      Este enlace vence en 30 minutos y solo puede utilizarse
                      una vez.
                    </p>

                    <p style="
                      margin: 12px 0 0;
                      color: #64748b;
                      font-size: 13px;
                      line-height: 1.6;
                    ">
                      Si no solicitaste este cambio, puedes ignorar este correo.
                      Tu contraseña actual seguirá siendo válida.
                    </p>

                    <hr style="
                      margin: 30px 0 20px;
                      border: 0;
                      border-top: 1px solid #e2e8f0;
                    " />

                    <p style="
                      margin: 0;
                      color: #94a3b8;
                      font-size: 12px;
                      line-height: 1.5;
                    ">
                      Este mensaje fue enviado automáticamente por SportFlow.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    resend.Emails.send({
        "from": f"{from_name} <{from_email}>",
        "to": [recipient_email],
        "subject": "Restablece tu contraseña de SportFlow",
        "html": html_content,
    })