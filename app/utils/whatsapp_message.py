######## INFOBIP ########

# from app.config.integration_config.whatsapp import whatsapp_channel
# from infobip_channels.whatsapp.models.body.text_message import TextMessageBody
# from app.utils.db_utils import get_registered_no_from_user_id

# def send_whatsapp_message(sender_id: str, recipient_id: str, message_text: str, logger):
#     try:
#         logger.info(f"Sending message to {recipient_id}: '{message_text}'")
#         message_body = TextMessageBody(
#             from_number=sender_id,
#             to=recipient_id,
#             content={
#                 "text": message_text,
#             }
#         )
#         resp = whatsapp_channel.send_text_message(message_body)
#         logger.info(f"Infobip API response for message to {recipient_id}: {resp}")
#     except Exception as e:
#         logger.error(f"Error sending message to {recipient_id}: {e}")

# async def send_upload_status_to_whatsapp(conn, user_id, logger, receiver_no, msg):
#     try:
#         user_registered_no = await get_registered_no_from_user_id(user_id, conn, logger) 
#         send_whatsapp_message(receiver_no, user_registered_no, msg, logger)
#         logger.info("Upload status sent successfully to WhatsApp")
#     except Exception as e:
#         logger.error(e)
#         raise  


####### META CLOUD API ########

from app.config.integration_config.whatsapp import whatsapp_channel

def send_whatsapp_message(recipient_no: str, message_text: str, logger):
    try:
        logger.info(f"Sending message to {recipient_no}: '{message_text}'")
        resp = whatsapp_channel.send_text_message(
            recipient_no=recipient_no,
            message_text=message_text
        )
        if resp:
            logger.info(f"Meta API response for message to {recipient_no}: {resp}")
        else:
            logger.warning(f"Failed to get a response from Meta API for message to {recipient_no}")

    except Exception as e:
        logger.error(f"Error sending message to {recipient_no}: {e}")

async def send_upload_status_to_whatsapp(userid, logger, receiver_no, msg):
    try:
        send_whatsapp_message(receiver_no, msg, logger)
        logger.info(f"Upload status sent successfully to WhatsApp user {userid}")
    except Exception as e:
        logger.error(f"Failed to send upload status to user {userid}: {e}")
        raise
    
async def mark_user_message_as_read(message_id: str, logger):
    try: 
        resp = whatsapp_channel.mark_message_as_read(message_id)
        if resp:
            logger.info(f"Successfully marked as read: {resp}")
        else:
            logger.warning(f"Failed to get a response from Meta API while performing mark as read.")
    except Exception as e:
        logger.error(f"Unable to mark message as read, {e}")

async def send_typing_indicator(message_id: str, logger):
    try: 
        resp = whatsapp_channel.send_typing_indicator(message_id)
        if resp:
            logger.info(f"Typing indicator is showing: {resp}")
        else:
            logger.warning(f"Failed to get a response from Meta API while sending typing indicator.")
    except Exception as e:
        logger.error(f"Unable to send the typing indicator, {e}")