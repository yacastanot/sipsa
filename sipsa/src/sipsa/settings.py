"""Configuración del proyecto Kedro."""
import os

from dotenv import load_dotenv
from kedro.config import OmegaConfigLoader
from omegaconf import OmegaConf

load_dotenv()  # Carga variables de .env en os.environ antes de que OmegaConf las resuelva

# Registra el resolver 'env' para usar ${env:VAR} en los archivos YAML de configuración
OmegaConf.register_new_resolver("env", lambda key: os.environ[key], replace=True)

CONFIG_LOADER_CLASS = OmegaConfigLoader

CONFIG_LOADER_ARGS = {
    "base_env": "base",
    "default_run_env": "local",
}
