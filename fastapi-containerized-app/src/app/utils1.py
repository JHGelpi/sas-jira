def get_current_time():
    from datetime import datetime
    return datetime.now()

def format_date(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

def log_message(message):
    print(f"[{format_date(get_current_time())}] {message}")

def validate_input(data, schema):
    from pydantic import BaseModel, ValidationError

    class InputSchema(BaseModel):
        __root__: schema

    try:
        InputSchema.parse_obj(data)
        return True
    except ValidationError as e:
        log_message(f"Validation error: {e}")
        return False

def generate_response(data, status_code=200):
    return {
        "status_code": status_code,
        "data": data
    }