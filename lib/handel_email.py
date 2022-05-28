import os.path
from email.message import EmailMessage
import smtplib
import mimetypes


def send_mail(from_, to_mail, username_server, pasword_server, subject,
              body="", file_attachments: list = None, smtp_ssl='smtp.gmail.com'):
    if file_attachments is None:
        file_attachments = []

    # Setup message
    message = EmailMessage()
    message['From'] = from_
    message['To'] = to_mail
    message['Subject'] = subject
    message.set_content(body)

    # Add attachments
    for file in file_attachments:
        mime_type, _ = mimetypes.guess_type(file)
        if mime_type is None:
            mime_type = "multipart/mixed"

        mime_type, mime_subtype = mime_type.split("/")
        with open(file, 'rb') as fp:
            message.add_attachment(fp.read(),
                                   maintype=mime_type,
                                   subtype=mime_subtype,
                                   filename=os.path.basename(file))

    # Login to mail server and send mail
    mail_server = smtplib.SMTP_SSL(smtp_ssl)
    mail_server.login(username_server, pasword_server)
    mail_server.send_message(message)
    mail_server.quit()
