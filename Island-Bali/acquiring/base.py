from abc import ABC, abstractmethod

class BaseBankClient(ABC):
    @abstractmethod
    def create_order(self, shop_id, order_data):
        pass

    @abstractmethod
    def get_order_info(self, shop_id, order_id):
        pass
