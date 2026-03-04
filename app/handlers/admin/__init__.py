from aiogram import Router
from .core import router as core_router
from .users import router as users_router
from .channels import router as channels_router
from .broadcast import router as broadcast_router

router = Router()

# Include all sub-routers
router.include_router(core_router)
router.include_router(users_router)
router.include_router(channels_router)
router.include_router(broadcast_router) 
