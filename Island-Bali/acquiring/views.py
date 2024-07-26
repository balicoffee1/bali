from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from acquiring.utils import RussianStandard

rus_standard = RussianStandard()


@swagger_auto_schema(

    operation_description="Этот запрос создаёт по переданным параметрам "
                          "оплаты счёт и генерирует"
                          "для отображения в виде предварительного"
                          "просмотра html-код письма счёта.",

    responses={200: "OK", 400: "Bad Request"},
    tags=["Эквайринг"],
    operation_id="Проверяет статус заказа")
@api_view(['GET'])
def get_link(request):
    """
    Этот запрос создаёт по переданным параметрам оплаты счёт и генерирует
     для отображения в виде предварительного
    просмотра html-код письма счёта.
    В ответ на данный запрос возвращается объект с полями invoice_id,
    содержащим уникальный номер созданного счёта,
    invoice_url , полный URL данного счёта, и invoice, где находится
    HTML-код предпросмотра e-mail сообщения, которое
    будет выслано клиенту:
    :param request:
"""

    payment = rus_standard.link_for_payment(42,
                                            'Иванов Иван Иваныч',
                                            'Заказ № 10',
                                            'test@example.com',
                                            'Услуга',
                                            '8 (910) 123-45-67')

    return Response(data=payment)


@swagger_auto_schema(
    operation_description="Метод `get_status_payment` "
                          "используется для проверки "
                          "статуса оплаты.",

    responses={200: "OK", 400: "Bad Request"},
    tags=["Эквайринг"],
    operation_id="Проверяет статус заказа")
@api_view(['GET'])
def get_status_payment(request, invoice_id):
    check_status = rus_standard.check_order(invoice_id)
    return Response(data=check_status)

# TODO подставить значение в линк payment
