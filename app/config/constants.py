CONCURRENCY_LIMIT_FOR_CSV_WORKER_TAKS = 5
NO_OF_CSV_WORKER_TASKS = 5
MAX_UPLOAD_RETRIES = 3
SAMPLE_ROW_LIMIT = 20
SCHEMA_BATCH_SIZE = 40

MAX_RETRY_ATTEMPTS = 3
MAX_EVAL_ITERATION = 3
INITIAL_RETRY_DELAY = 1000  # milliseconds

CSV_NOTIFY_CHANNEL = 'csv_job'
EXCEL_NOTIFY_CHANNEL = 'excel_job'

DATA_TIME_FORMAT = """
    Date Only:
    - YYYY-MM-DD
    - MM-DD-YYYY
    - DD-MM-YYYY
    - YYYY/MM/DD
    - MM/DD/YYYY
    - DD/MM/YYYY

    Time Only:
    - HH:mm
    - HH:mm:ss
    - HH:mm:ss.SSS
    - HH:mm:ss.SSSSSS

    Date + Time (no timezone):
    - YYYY-MM-DD HH:mm:ss
    - YYYY-MM-DD HH:mm:ss.SSS
    - YYYY-MM-DD HH:mm:ss.SSSSSS
    - MM-DD-YYYY HH:mm:ss
    - MM-DD-YYYY HH:mm:ss.SSS
    - DD-MM-YYYY HH:mm:ss
    - DD-MM-YYYY HH:mm:ss.SSS
    - YYYY/MM/DD HH:mm:ss
    - YYYY/MM/DD HH:mm:ss.SSS
    - MM/DD/YYYY HH:mm:ss
    - MM/DD/YYYY HH:mm:ss.SSS
    - DD/MM/YYYY HH:mm:ss
    - DD/MM/YYYY HH:mm:ss.SSS

    Date + Time + Timezone:
    - YYYY-MM-DD HH:mm:ss [UTC]
    - YYYY-MM-DD HH:mm:ss.SSS [UTC]
    - YYYY-MM-DD HH:mm:ss.SSSSSS [UTC]
    - YYYY-MM-DD HH:mm:ss Z
    - YYYY-MM-DD HH:mm:ss.SSS Z
    - YYYY-MM-DD HH:mm:ss.SSSSSS Z
    - YYYY-MM-DDTHH:mm:ssZ
    - YYYY-MM-DDTHH:mm:ss.SSSZ
    - YYYY-MM-DDTHH:mm:ss.SSSSSSZ
"""