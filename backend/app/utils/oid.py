from bson import ObjectId

def generate_oid():
    return str(ObjectId())