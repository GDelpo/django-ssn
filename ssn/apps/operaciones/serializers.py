import logging
import uuid

from django.db import models
from rest_framework import serializers

from .models import BaseRequestModel, TipoEspecie

# Configuración del logger
logger = logging.getLogger("operaciones")


def transform_representation(data):
    """
    Transforma las claves de un diccionario a camelCase.
    Si el valor es None, lo reemplaza por cadena vacía.
    Convierte UUIDs a strings.

    Args:
        data (dict): Diccionario con datos a transformar

    Returns:
        dict: Diccionario con claves en camelCase y valores transformados
    """
    from .helpers import to_camel_case

    transformed = {}
    for k, v in data.items():
        key = to_camel_case(k)
        if v is None:
            transformed[key] = ""
        elif isinstance(v, uuid.UUID):
            transformed[key] = str(v)
        else:
            transformed[key] = v

    logger.debug(f"Transformación camelCase completada: {len(data)} campos procesados")
    return transformed


class CustomDateField(serializers.DateField):
    """
    Campo de fecha personalizado que formatea las fechas al formato DDMMYYYY.
    Útil para sistemas externos que requieren este formato específico.
    """

    def to_representation(self, value):
        """
        Convierte la fecha al formato DDMMYYYY.

        Args:
            value (date): Fecha a formatear

        Returns:
            str: Fecha formateada o None
        """
        formatted = value.strftime("%d%m%Y") if value else None
        logger.debug(f"Fecha formateada: {value} -> {formatted}")
        return formatted


class CustomBooleanField(serializers.BooleanField):
    """
    Campo booleano personalizado que convierte valores booleanos a "1" o "0" (string).
    Utilizado para compatibilidad con servicios externos que esperan strings.
    """

    def to_representation(self, value):
        """
        Convierte el valor booleano a "1" o "0".

        Args:
            value (bool): Valor booleano a formatear

        Returns:
            str: "1" para True, "0" para False
        """
        formatted = "1" if value else "0"
        logger.debug(f"Valor booleano formateado: {value} -> {formatted}")
        return formatted


class CamelCaseModelSerializer(serializers.ModelSerializer):
    """
    Serializador base que transforma la representación de los datos a camelCase.
    Además, redefine los campos de fecha para utilizar CustomDateField.
    """

    def to_representation(self, instance):
        """
        Personaliza la representación de los datos, aplicando reglas específicas
        para ciertos tipos de campos y transformando las claves a camelCase.

        Args:
            instance: Instancia del modelo a serializar

        Returns:
            dict: Datos serializados con claves en camelCase
        """
        original = super().to_representation(instance)

        # Determinar si es FCI para saber si aplica decimales en cantidades
        is_fci = (
            hasattr(instance, "tipo_especie")
            and instance.tipo_especie == TipoEspecie.FONDOS_COMUNES_DE_INVERSIÓN
        )

        # =====================================================================
        # FORMATEO DE CAMPOS NUMÉRICOS SEGÚN ESPECIFICACIONES SSN
        # =====================================================================

        # --- Campos de cantidad de especies (14,6): 6 decimales solo para FC ---
        cantidad_fields = ["cant_especies", "cantidad_devengado_especies", "cantidad_percibido_especies"]
        for field in cantidad_fields:
            if field in original and original[field] is not None:
                if is_fci:
                    # FCI: mantener decimales (hasta 6)
                    original[field] = str(original[field])
                else:
                    # Otros: solo enteros
                    original[field] = str(int(float(original[field])))

        # --- Campos enteros sin decimales (Number 10, 14, etc.) ---
        integer_fields = [
            "valor_contable", "prevision_desvalorizacion", "valor_financiero",
            "valor_nominal_origen", "valor_nominal_nacional", "valor_nominal",
            "valor_adquisicion"
        ]
        for field in integer_fields:
            if field in original and original[field] is not None:
                original[field] = str(int(float(original[field])))

        # --- Tasa (2,3): mantener hasta 3 decimales ---
        if "tasa" in original and original["tasa"] is not None:
            # Formatear con hasta 3 decimales, sin ceros innecesarios
            tasa_val = float(original["tasa"])
            if tasa_val == int(tasa_val):
                original["tasa"] = str(int(tasa_val))
            else:
                original["tasa"] = str(round(tasa_val, 3)).rstrip('0').rstrip('.')

        # --- Precio pase VT (6,2): hasta 2 decimales ---
        if "precio_pase_vt" in original and original["precio_pase_vt"] is not None:
            precio_val = float(original["precio_pase_vt"])
            if precio_val == int(precio_val):
                original["precio_pase_vt"] = str(int(precio_val))
            else:
                original["precio_pase_vt"] = str(round(precio_val, 2)).rstrip('0').rstrip('.')

        transformed = transform_representation(original)

        if hasattr(instance, "pk"):
            logger.debug(
                f"Serialización completada para instancia ID: {instance.pk}, modelo: {instance.__class__.__name__}"
            )

        return transformed

    def build_standard_field(self, field_name, model_field):
        """
        Personaliza la construcción de campos estándar, reemplazando
        campos de fecha por CustomDateField.

        Args:
            field_name: Nombre del campo
            model_field: Campo del modelo

        Returns:
            tuple: (clase del campo, argumentos del campo)
        """
        field_class, field_kwargs = super().build_standard_field(
            field_name, model_field
        )
        if isinstance(model_field, (models.DateField, models.DateTimeField)):
            field_class = CustomDateField
            logger.debug(f"Campo de fecha personalizado aplicado: {field_name}")
        elif isinstance(model_field, models.BooleanField):
            field_class = CustomBooleanField
            logger.debug(f"Campo booleano personalizado aplicado: {field_name}")

        return field_class, field_kwargs


class BaseModelSerializer(CamelCaseModelSerializer):
    """
    Serializador para BaseRequestModel.
    Se excluyen campos específicos para evitar exponerlos en la serialización.
    """

    class Meta:
        model = BaseRequestModel
        exclude = ["uuid", "send_at", "created_at", "updated_at", "estado"]


def create_model_serializer(tipo_operacion):
    """
    Crea dinámicamente un serializador para el modelo correspondiente
    al tipo de operación especificado.

    Args:
        tipo_operacion (str): Código del tipo de operación

    Returns:
        class: Clase de serializador específica para el tipo de operación

    Raises:
        ValueError: Si el tipo de operación no es válido
    """
    from .helpers import get_mapping_model

    logger.debug(f"Creando serializador para tipo de operación: {tipo_operacion}")

    mapping = get_mapping_model()
    model_class = mapping.get(tipo_operacion)

    if not model_class:
        logger.error(f"Tipo de operación no válida: {tipo_operacion}")
        raise ValueError(f"Tipo de operación no válida: {tipo_operacion}")

    # Determinar campos a excluir según el tipo de operación
    # Los stocks mensuales no tienen campo 'comprobante' y excluyen timestamps
    if tipo_operacion in ["SI", "SP", "SC"]:
        exclude_fields = ["id", "solicitud", "created_at", "updated_at"]
    else:
        # Operaciones semanales también excluyen timestamps
        exclude_fields = ["id", "comprobante", "solicitud", "created_at", "updated_at"]

    class DynamicModelSerializer(CamelCaseModelSerializer):
        """
        Serializador dinámico para un tipo específico de operación.
        """

        class Meta:
            model = model_class
            exclude = exclude_fields

    logger.debug(f"Serializador creado para modelo: {model_class.__name__}")
    return DynamicModelSerializer


def serialize_operations(base_instance, operations, pre_serialized=False):
    """
    Serializa una instancia base y las operaciones/stocks asociadas.

    Para entregas semanales: usa el campo "operaciones" con todas las operaciones.
    Para entregas mensuales: usa el campo "stocks" con todos los stocks (cada uno con su "tipo").

    Args:
        base_instance: Instancia del modelo base (BaseRequestModel)
        operations: Lista de operaciones/stocks a serializar (instancias reales de modelo)
        pre_serialized (bool): Indica si las operaciones ya están serializadas

    Returns:
        dict: Datos serializados con la instancia base y sus operaciones/stocks
    """
    from .models import TipoEntrega

    logger.info(
        f"Serializando solicitud {base_instance.uuid} con {len(operations)} operaciones/stocks"
    )

    base_data = BaseModelSerializer(base_instance).data
    is_monthly = base_instance.tipo_entrega == TipoEntrega.MENSUAL

    if pre_serialized:
        logger.debug("Usando operaciones pre-serializadas")
        if is_monthly:
            base_data["stocks"] = operations
        else:
            base_data["operaciones"] = operations
    else:
        logger.debug("Serializando cada operación/stock individualmente")

        if is_monthly:
            # Para entregas mensuales: un único array "stocks" con campo "tipo" en cada uno
            stocks = []

            for op in operations:
                try:
                    tipo_op = getattr(op, "tipo_operacion", None)
                    tipo_stock = getattr(op, "tipo", None)  # I, P, o C para SSN
                    
                    if tipo_op is None:
                        logger.warning(
                            f"No se encontró tipo_operacion para instancia {op}."
                        )
                        continue

                    serializer_class = create_model_serializer(tipo_op)
                    serialized_data = serializer_class(op).data
                    
                    # El campo "tipo" ya viene del modelo (I=Inversión, P=PlazoFijo, C=Cheque)
                    # Asegurarse de que esté al principio
                    if "tipo" not in serialized_data:
                        serialized_data["tipo"] = tipo_stock
                    
                    stocks.append(serialized_data)
                    logger.debug(f"Stock tipo {tipo_stock} serializado correctamente")
                except Exception as e:
                    logger.error(f"Error al serializar stock: {str(e)}")

            base_data["stocks"] = stocks
            logger.debug(f"Total stocks serializados: {len(stocks)}")
        else:
            # Estructura original para entregas semanales
            serialized_ops = []

            for op in operations:
                try:
                    tipo = getattr(op, "tipo_operacion", None)
                    if tipo is None:
                        logger.warning(
                            f"No se encontró tipo_operacion para instancia {op}."
                        )
                        continue

                    serializer_class = create_model_serializer(tipo)
                    serialized_data = serializer_class(op).data
                    serialized_ops.append(serialized_data)
                    logger.debug(f"Operación tipo {tipo} serializada correctamente")
                except Exception as e:
                    logger.error(f"Error al serializar operación: {str(e)}")

            base_data["operaciones"] = serialized_ops
            logger.debug(f"Total de operaciones serializadas: {len(serialized_ops)}")

    return base_data
