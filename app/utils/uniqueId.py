import uuid 

def generate_unique_id():
    return uuid.uuid4().hex  # 32-character hex string

def str_to_uuid(id):
    return uuid.UUID(hex=id)