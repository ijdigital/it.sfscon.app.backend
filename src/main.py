# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2023 Digital CUBE <https://digitalcube.rs>

import logging
import dotenv
import importlib
from shared.setup_logger import setup_redis_logger, setup_file_logger

from app import get_app

app = get_app()

def import_modules(svcs):
    dotenv.load_dotenv()
    setup_redis_logger()

    for svc in svcs:
        svc_name = svc.split('.')[0]
#        setup_file_logger(svc_name)
        importlib.reload(importlib.import_module(svc))



import_modules(['conferences.api'])

if __name__ == "__main__":
    import uvicorn
    setup_file_logger('conference')
    log = logging.getLogger('conference_logger')
    log.info("STARTING")
    uvicorn.run(get_app(), host="0.0.0.0", port=8000)
