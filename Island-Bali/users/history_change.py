from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from users.models import UserCard
from users.serializers import UserCardSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_bank_card(request):
    try:
        user = request.user
        card_data = request.data

        card_number = card_data["card_number"]
        expiration_date = card_data["expiration_date"]

        UserCard.create_new_card(user, card_number, expiration_date)

        return Response("Card added successfully",
                        status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bank_cards(request):
    try:
        user = request.user
        user_cards = UserCard.objects.filter(user=user)
        serializer = UserCardSerializer(user_cards, many=True)

        serialized_data = serializer.data
        return Response(serialized_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_bank_card(request):
    try:
        user = request.user
        values = request.data
        card_id = values["card_id"]
        card = UserCard.objects.get(id=card_id, user=user)
        card.delete()
        return Response("Card deleted successfully",
                        status=status.HTTP_204_NO_CONTENT)
    except UserCard.DoesNotExist:
        return Response(
            "Card does not exist or you don't have permission to delete "
            "it",
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        return Response(f"Error: {e}", status=status.HTTP_400_BAD_REQUEST)
