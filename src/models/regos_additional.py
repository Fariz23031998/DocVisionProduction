from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

class ItemType(str, Enum):
    """Тип номенклатуры"""
    ITEM = "Item"
    SERVICE = "Service"
    # Alternative numeric values
    ITEM_NUM = "1"
    SERVICE_NUM = "2"


class Origin(str, Enum):
    """Происхождение товара"""
    NOT_SPECIFIED = "NotSpecified"
    BUYING_AND_SELLING = "BuyingAndSelling"
    PRODUCED = "Produced"
    SERVICE = "Service"
    # Alternative numeric values
    NOT_SPECIFIED_NUM = "-1"
    BUYING_AND_SELLING_NUM = "0"
    PRODUCED_NUM = "1"
    SERVICE_NUM = "2"


class RegosProductUpdate(BaseModel):
    """
    Модель для редактирования номенклатуры в системе Regos.
    Endpoint: [POST] .../v1/Item/Edit
    """

    # Required fields
    id: int = Field(..., description="ID номенклатуры")

    # Optional fields
    group_id: Optional[int] = Field(None, description="ID группы номенклатуры. По умолчанию 0 - корневая группа")
    department_id: Optional[int] = Field(None, description="ID отдела, к которому принадлежит номенклатура")
    vat_id: Optional[int] = Field(None, description="ID ставки НДС")
    unit_id: Optional[int] = Field(None, description="ID единицы измерения номенклатуры")
    unit2_id: Optional[int] = Field(None, description="ID единицы измерения номенклатуры для КДТ")
    color_id: Optional[int] = Field(None, description="ID цвета номенклатуры")
    size_id: Optional[int] = Field(None, description="ID размера номенклатуры")
    brand_id: Optional[int] = Field(None, description="ID бренда номенклатуры")
    producer_id: Optional[int] = Field(None, description="ID производителя номенклатуры")
    country_id: Optional[int] = Field(None, description="ID страны производства номенклатуры")
    parent_id: Optional[int] = Field(None,
                                     description="ID родительской номенклатуры (используется для создания размерной сетки)")

    type: Optional[ItemType] = Field(None, description="Тип номенклатуры: Item (1) - Товар, Service (2) - Услуга")
    code: Optional[int] = Field(None, description="Код номенклатуры")
    name: Optional[str] = Field(None, description="Наименование номенклатуры")
    fullname: Optional[str] = Field(None, description="Полное наименование номенклатуры")
    description: Optional[str] = Field(None, description="Дополнительное описание номенклатуры")
    articul: Optional[str] = Field(None, description="Артикул номенклатуры")
    kdt: Optional[int] = Field(None, description="Количество номенклатуры для КДТ")
    min_quantity: Optional[int] = Field(None, description="Минимальное количество номенклатуры")
    icps: Optional[str] = Field(None, description="ИКПУ - идентификационный код продукции и услуг")

    assemblable: Optional[bool] = Field(None, description="Метка о том, что товар можно произвести")
    disassemblable: Optional[bool] = Field(None, description="Метка о том, что товар можно разобрать")
    is_labeled: Optional[bool] = Field(None, description="Метка о том, что товар подлежит маркировке")

    comission_tin: Optional[str] = Field(None, description="ИНН комиссионера")
    package_code: Optional[str] = Field(None, description="Код упаковки")
    origin: Optional[Origin] = Field(None, description="Происхождение товара")
    partner_id: Optional[int] = Field(None, description="ID контрагента")



class RegosProductBatchEditRequest(BaseModel):
    """
    Один запрос редактирования номенклатуры для батчевого вызова.
    """
    key: str
    payload: RegosProductUpdate = Field(..., description="Данные для редактирования номенклатуры")

class RegosProductBatchEdit(BaseModel):
    """
    Пакетная модель для редактирования нескольких номенклатур.
    """
    requests: List[RegosProductBatchEditRequest] = Field(
        ..., max_items=50, description="Массив редактированных номенклатуры"
    )


class RegosBarcodeCreate(BaseModel):
    item_id: int
    barcode_type_id: int = 1
    value: str
    forced: bool = False



class RegosBarcodeBatchAddRequest(BaseModel):
    """
    Один запрос добавление штрих-кодов для батчевого вызова.
    """
    key: str
    payload: RegosBarcodeCreate = Field(..., description="Данные для добавление баркода")

class RegosBarcodeBatchAdd(BaseModel):
    """
    Пакетная модель для редактирования нескольких номенклатур.
    """
    requests: List[RegosBarcodeBatchAddRequest] = Field(
        ..., max_items=50, description="Массив добавления баркодов"
    )