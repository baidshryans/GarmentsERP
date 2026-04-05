from django.db.models.signals import post_save,pre_save
from django.dispatch import receiver

from inventory.models import RawMaterialInventory, UnBarcodedDetails, UnBarcodedMain
from manufacturing.models import HallmarkIssueDetails, HallmarkIssueItem, HallmarkReceiveDetails, HallmarkReceiveItem, KarigarGoldIssue, KarigarReceiveItem, KarigarReceiveItemDetails, KarigarStoneIssue

@receiver(post_save, sender=KarigarReceiveItem)
def create_unbarcoded_inventory(sender, instance, created, **kwargs):
    """
    Automatically creates an UnbarcodedMain entry whenever a KarigarReceiveItem is created.
    """
    if created:  # Only create on new instance
        unbarcoded_data = {
            "item": instance.item,
            "item_desc": str(instance.item),
            "pcs": instance.pcs,
            "gw": instance.gw,
            "nw": instance.nw,
            "purity": instance.purity,
            "value": None,  # Set appropriate value logic
            "making_val": instance.making,
            "making_type": None,  # Set appropriate making type logic
            "other_chg": None,  # Set additional charge logic if needed
            "design_code": None,  # Set design code logic
            "kr_code": None,  # Set appropriate karigar code logic
            "total_amount": 0,  # Adjust based on pricing logic
            "size": None,  # Set appropriate size logic if applicable
            "metal_color": None,  # Set appropriate metal color logic
            "created_from": "KarigarReceiveItem",
            "customer_order": None,  # Link to customer order if applicable
            "created_by": "System",  # Adjust to capture user creating the entry
            "stk_status": True,
            "voucher_no": None,  # Set voucher number if applicable
            "retail": instance.retail  # Maintain retail linkage
        }
        
        ubm = UnBarcodedMain.objects.create(**unbarcoded_data)
        for item in instance.ref_job_sl_no.issued_sample_items.all():
            item.next = ubm
            item.save()
        instance.unbarcoded_item = ubm
        instance.save()


@receiver(post_save, sender=KarigarReceiveItemDetails)
def create_unbarcoded_inventory_details(sender, instance: KarigarReceiveItemDetails, created, **kwargs):
    """
    Automatically creates an UnBarcodedDetails entry whenever a KarigarReceiveItemDetails is created.
    """
    if created:
        unbarcoded_details_data = {
            "main_item": instance.main_sl_no.unbarcoded_item,
            "item": instance.item,
            "pcs": instance.balance_pcs,
            "gw": instance.balance_gw,
            "ct": instance.balance_ct,
            "rate":instance.rate,
            "amt":instance.amt,
            "packet": instance.packet
        }
        UnBarcodedDetails.objects.create(**unbarcoded_details_data)

# @receiver(post_save, sender=HallmarkReceiveItem)
# def create_unbarcoded_inventory_from_hallmark(sender, instance:HallmarkReceiveItem, created, **kwargs):
#     """
#     Automatically creates an UnbarcodedMain entry whenever a HallmarkReceiveItem is created.
#     """
#     if created:  # Only create on new instance
#         unbarcoded_data = {
#             "item": instance.item,
#             "item_desc": str(instance.item),
#             "pcs": instance.pcs,
#             "gw": instance.gw,
#             "nw": instance.nw,
#             "purity": instance.purity,
#             "huid":instance.huid,
#             "value": None,  # Set appropriate value logic
#             "making_val": None,  # Set appropriate making value logic
#             "making_type": None,  # Set appropriate making type logic
#             "other_chg": None,  # Set additional charge logic if needed
#             "design_code": None,  # Set design code logic
#             "kr_code": None,  # Set appropriate karigar code logic
#             "total_amount": 0,  # Adjust based on pricing logic
#             "size": None,  # Set appropriate size logic if applicable
#             "metal_color": None,  # Set appropriate metal color logic
#             "created_from": "HallmarkIssueItem",
#             "customer_order": None,  # Link to customer order if applicable
#             "created_by": "System",  # Adjust to capture user creating the entry
#             "stk_status": True,
#             "voucher_no": None,  # Set voucher number if applicable
#             "retail": instance.retail  # Maintain retail linkage
#         }
        
#         ubm = UnBarcodedMain.objects.create(**unbarcoded_data)
#         instance.unbarcoded_item = ubm
#         instance.save()


# @receiver(post_save, sender=HallmarkReceiveDetails)
# def create_unbarcoded_inventory_details_from_hallmark(sender, instance: HallmarkReceiveDetails, created, **kwargs):
#     """
#     Automatically creates an UnBarcodedDetails entry whenever a HallmarkReceiveDetails is created.
#     """
#     if created:
#         unbarcoded_details_data = {
#             "main_item": instance.main_item.unbarcoded_item,
#             "item": instance.main_item.item,
#             "pcs": instance.pcs,
#             "gw": instance.gw,
#             "ct": instance.ct,
#             "rate": None,  # Set rate logic if applicable
#             "amt": None,  # Set amount logic if applicable
#             "packet": instance.packet
#         }
#         UnBarcodedDetails.objects.create(**unbarcoded_details_data)


# @receiver(pre_save, sender=KarigarGoldIssue)
# def capture_karigar_gold_issue_data(sender, instance: KarigarGoldIssue, **kwargs):
#     """
#     Captures KarigarGoldIssue data before saving
#     """
#     if not instance.pk:  
#         rm_item = RawMaterialInventory.objects.get(item=instance.item)
#         rm_item.gw = rm_item.gw - instance.item_gw
#         rm_item.save()

# @receiver(pre_save, sender=KarigarStoneIssue)
# def capture_karigar_stone_issue_data(sender, instance:KarigarStoneIssue, **kwargs):
#     print("*"*40)
#     print("Presave called ")
#     print("*"*40)
#     """
#     Captures KarigarStoneIssue data before saving
#     """
#     if not instance.pk:  # Only for new instances
#         # You can add any pre-save logic here
#         # For example, logging or data validation
#         rm_item = RawMaterialInventory.objects.get(item=instance.item)
#         rm_item.gw = rm_item.gw - instance.gw
#         rm_item.ct = rm_item.ct - instance.ct
#         rm_item.pcs = rm_item.pcs - instance.pcs
#         rm_item.save()
#         print(f"About to save KarigarStoneIssue: {instance.__dict__}")

