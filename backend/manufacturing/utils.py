from accounting.utils import increment_series_no, get_next_bill_number
from .models import *
from django.http import HttpResponse, JsonResponse
from rest_framework import serializers
class CustomerOrderItemforIssueSerializer(serializers.ModelSerializer):
    customer_order_item = serializers.SerializerMethodField()
    item = serializers.SerializerMethodField()
    class Meta:
        model = CustomerOrderItems
        fields = ["customer_order_item","item","pcs","purity","remarks","size"]


    def get_customer_order_item(self,obj):
        return obj.id

    def get_item(self,obj):
        return obj.item_id.short_code

    def to_representation(self, instance):
        # Get the original representation
        representation = super().to_representation(instance)

        # Modify the price field
        representation['purity'] = instance.purity.purity

        return representation

def generate_gold_issue_billno(retail):
    return get_next_bill_number(retail, 'IV/GL')

def generate_stone_issue_billno(retail):
    return get_next_bill_number(retail, 'IV/STN')

def generate_stone_rec_billno(retail):
    return get_next_bill_number(retail, 'REC/STN')

def generate_hallmark_issue_bill(retail):
    return get_next_bill_number(retail, 'HMIS')

def generate_hallmark_rec_bill(retail):
    return get_next_bill_number(retail, 'HM/RE')

def generate_refinary_iss_bill(retail):
    return get_next_bill_number(retail, 'REF/ISS')

def generate_refinary_rec_bill(retail):
    return get_next_bill_number(retail, 'REF/REC')

def generate_melting_iss_bill(retail):
    return get_next_bill_number(retail, 'MLT/ISS')

def generate_melting_rec_bill(retail):
    return get_next_bill_number(retail, 'MLT/REC')

def generate_assay_iss_bill(retail):
    return get_next_bill_number(retail, 'ASY/ISS')

def generate_assay_rec_bill(retail):
    return get_next_bill_number(retail, 'ASY/REC')

def generate_slip_no(retail):
    return get_next_bill_number(retail, 'IV')

def generate_stock_transfer_billno(retail):
    return get_next_bill_number(retail, 'RST')


def fetch_sl_no(request):
    order_no = request.GET.get('order_no_id')
    sl_no_list = CustomerOrderItems.objects.filter(order_no = order_no,del_status=False).values('sl_no')

    return JsonResponse({'sl_no_list': list(sl_no_list)})


def fetch_order_details(request):
    order_no_id = request.GET.get('order_no_id')
    sl_no = request.GET.get('sl_no')
    try:
        order_item = CustomerOrderItems.objects.get(order_no_id=order_no_id, sl_no=sl_no)
        
        item_data = {
            'customer_order_item':order_item.id,
            'design_no': '',  # Assuming you have a design_no field
            'main_item_id': order_item.item_id.id,  # item_id as the id itself (Integer)
            'main_item_short_code': order_item.item_id.short_code,  # Access short_code from the related Item model
            'purity_id': order_item.purity_id,  # Assuming purity is a ForeignKey, get the id
            'pcs': order_item.pcs,
            'app_wt': order_item.gw,
            'due_date': '',  # Format the date
            'size': order_item.size,
            'remarks': order_item.remarks,
            'rec_status': order_item.rec_status
        }
        
        return JsonResponse({'success': True, 'item_data': CustomerOrderItemforIssueSerializer(order_item).data})
    except CustomerOrderItems.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Item not found.'})
    
def generate_kr_rec_slip_no(retail):
    return get_next_bill_number(retail, 'RS')





def get_kr_receive_slip_numbers(request):
    kr_id = request.GET.get('kr_id')
    if kr_id:
        slips = KarigarReceive.objects.filter(karigar_ldgr=kr_id).values('receive_slip_no','id' )
        return JsonResponse({"slip_numbers": list(slips)})
    return JsonResponse({"slip_numbers": []})

def get_kr_receive_sl_no(request):
    rec_id = request.GET.get('rec_id')
    items = KarigarReceiveItem.objects.filter(receive_slip_no = rec_id).values('id','sl_no')
    return JsonResponse({"slip_items": list(items)})

def fetch_receive_item_details(request):
    rec_sl_no = request.GET.get('rec_sl_no')
    rec_no = request.GET.get('rec_no')
    item = KarigarReceiveItem.objects.get(receive_slip_no=rec_no, sl_no=rec_sl_no).values('id', 'sl_no', 'item_id', 'item_id__short_code', 'item_id__description', 'pcs', 'gw', 'nw', 'kr_code')
    item_details = KarigarReceiveItemDetails.objects.filter(main_sl_no=item[0]['id']).values('id', 'packet__packet_no','packet__id','balance_pcs','balance_ct','balance_gw')
    item_with_details = {
        'item': item[0],
        'details': list(item_details)
    }
    return JsonResponse({"item_with_details": item_with_details})

def create_or_update_nested(serializer_class, parent_instance, related_name,parent_name, nested_data):
    """
    Generic function to create or update nested objects.

    Args:
        serializer_class (Serializer): The serializer class for the nested object.
        parent_instance (Model): The parent instance to link the nested objects to.
        related_name (str): The related name of the nested field (e.g., 'children', 'grandchildren').
        nested_data (list): List of dictionaries with nested data.

    Returns:
        None
    """
    related_manager = getattr(parent_instance, related_name)
    existing_objects = {obj.id: obj for obj in related_manager.all()}
    instances = []
    for item_data in nested_data:
        obj_id = item_data.get("id")
        if obj_id and (obj_id in existing_objects):
            # Update the existing object
            serializer_instance = serializer_class(instance=existing_objects.pop(obj_id), data=item_data, partial=True)
            serializer_instance.is_valid(raise_exception=True)
            instances.append(serializer_instance.save())
        else:
            # Create a new object and link it
            # item_data[parent_name] = parent_instance
            serializer_instance = serializer_class(data=item_data)
            serializer_instance.is_valid(raise_exception=True)
            instances.append(serializer_instance.save(**{parent_name : parent_instance}))

    # Delete any remaining objects not in the new data
    if existing_objects:
        print(f"[COUN-DELETE] related_name={related_name} deleting ids={list(existing_objects.keys())}")
    for obj in existing_objects.values():
        obj.delete()
    return instances


def resolve_huid_for_receive_item(rec_item, max_hops=10):
    """Resolve the HUID for a KarigarReceiveItem, walking back through sample
    re-issues when the piece had been hallmarked on an earlier receive cycle.

    Per hop, in order:
      1. Direct: HallmarkReceiveItem.receive_sl == current.
      2. Legacy fallback: HallmarkIssueItem.receive_sl == current, then look up
         a HallmarkReceiveItem under the same HallmarkIssue (covers rows where
         HallmarkReceiveItem.receive_sl was never populated).
      3. Sample fast path: current.ref_sample_issue_item.huid (if non-empty).
      4. Walk back: follow current.ref_sample_issue_item.kr_receive_item to the
         prior KarigarReceiveItem and recurse.

    Returns the HUID string or None. Cycle-safe and capped at max_hops.
    """
    if rec_item is None:
        return None
    visited = set()
    current = rec_item
    for _ in range(max_hops):
        if current is None or current.pk in visited:
            return None
        visited.add(current.pk)

        # 1. Direct hallmark receive FK
        hri = (
            HallmarkReceiveItem.objects
            .filter(receive_sl=current, huid__isnull=False)
            .exclude(huid='')
            .order_by('-id')
            .first()
        )
        if hri:
            return hri.huid

        # 2. Legacy fallback via HallmarkIssueItem
        issue_ids = list(
            HallmarkIssueItem.objects
            .filter(receive_sl=current)
            .values_list('issue_slip_no_id', flat=True)
        )
        if issue_ids:
            hri = (
                HallmarkReceiveItem.objects
                .filter(issue_slip_no_id__in=issue_ids, huid__isnull=False)
                .exclude(huid='')
                .order_by('-id')
                .first()
            )
            if hri:
                return hri.huid

        # 3. Sample re-issue fast path
        sii = getattr(current, 'ref_sample_issue_item', None)
        if sii is None:
            return None
        if sii.huid:
            return sii.huid

        # 4. Walk back to the prior KarigarReceiveItem via the sample's source FK
        if not sii.kr_receive_item_id:
            return None
        current = sii.kr_receive_item

    return None
