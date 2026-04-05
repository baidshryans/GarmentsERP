from accounting.utils import get_next_bill_number
from .models import *
from django.http import HttpResponse, JsonResponse
from decimal import Decimal
from django.db.models import Sum, F
from manufacturing.models import *


def generate_po_no():
    # Legacy fallback for non-retail calls
    last_issue = PurchaseOrder.objects.order_by('id').last()
    if not last_issue:
        return "PO/2324/00001"
    po_no = last_issue.po_no
    po_no_suffix = int(po_no.split('/')[-1])
    new_po_no_suffix = po_no_suffix + 1
    new_po_no = f"PO/2324/{new_po_no_suffix:05}"
    return new_po_no


def generate_pv_no():
    # Legacy fallback for non-retail calls
    last_issue = PurchaseVoucher.objects.order_by('id').last()
    if not last_issue:
        return "PV/2324/00001"
    pv_no = last_issue.billno
    pv_no_suffix = int(pv_no.split('/')[-1])
    new_pv_no_suffix = pv_no_suffix + 1
    new_pv_no = f"PV/2324/{new_pv_no_suffix:05}"
    return new_pv_no


def generate_next_pur_voucher_no(retail):
    return get_next_bill_number(retail, "PV")


def generate_next_pur_return_no(retail):
    return get_next_bill_number(retail, "PR")


def generate_next_pur_order_no(retail):
    return get_next_bill_number(retail, "PO")

def fetch_po_sl_no(po_no):
    #po_no = request.GET.get('po_no_id')
    po_sl_no_list = PurchaseOrderItems.objects.filter(po_slip=po_no).values('po_sl_no', 'id')  # Include 'id'
    po_sl_no_list_with_id = [{'po_sl_no': item['po_sl_no'], 'id': item['id']} for item in po_sl_no_list]
    return JsonResponse({'po_sl_no_list': po_sl_no_list_with_id})

def fetch_po_items(po_no):
    #po_no = request.GET.get('po_no_id')
    po_item = PurchaseOrderItems.objects.get(id=po_no)

    # Query for stone issues
    stone_issue = KarigarStoneIssue.objects.filter(job_sl_object_id=po_item.id) \
        .values('packet__pckt_no', 'packet', 'packet__shape__shape_name', 'packet__stone_item_id__short_code', 
                'packet__stone_item_id__item_name', 'packet__stone_item_id', 'packet__rate_for_retail', 
                'packet__stone_item_id__uom') \
        .annotate(
            pcs=Sum('pcs'),
            gw=Sum('gw'),
            ct=Sum('ct')
        )
    
    # Query for stone receives
    stone_receive = KarigarStoneReceive.objects.filter(job_sl_object_id=po_item.id) \
        .values('packet__pckt_no', 'packet', 'packet__shape__shape_name', 'packet__stone_item_id__short_code', 
                'packet__stone_item_id__item_name', 'packet__stone_item_id', 'packet__rate_for_retail', 
                'packet__stone_item_id__uom') \
        .annotate(
            return_pcs=Sum('return_pcs'),
            return_gw=Sum('return_gw'),
            return_ct=Sum('return_ct'),
            broken_pcs=Sum('broken_pcs'),
            broken_gw=Sum('broken_gw'),
            broken_ct=Sum('broken_ct'),
            loss_pcs=Sum('loss_pcs'),
            loss_gw=Sum('loss_gw'),
            loss_ct=Sum('loss_ct')
        )

    # Convert querysets to dictionaries based on packet number
    stone_issue_dict = {issue['packet__pckt_no']: issue for issue in stone_issue}
    stone_receive_dict = {recv['packet__pckt_no']: recv for recv in stone_receive}
    itm_value = 0

    # Combine both datasets into one result
    combined_data = []

    # Start with stone issue data and merge stone receive data if available
    for pckt_no, issue_data in stone_issue_dict.items():
        uom = issue_data.get('packet__stone_item_id__uom', 'ct')  # Default UOM to 'ct'

        combined_entry = {
            'packet_item_id': issue_data.get('packet__stone_item_id'),
            'packet_id': issue_data.get('packet'),
            'packet__pckt_no': pckt_no,
            'packet_item': issue_data.get('packet__stone_item_id__short_code'),
            'packet_item_name': issue_data.get('packet__stone_item_id__item_name'),
            'shape': issue_data.get('packet__shape__shape_name', ''),
            'pcs': issue_data.get('pcs', 0),
            'gw': issue_data.get('gw', 0),
            'ct': issue_data.get('ct', 0),
            'uom': uom,
            # Default values for the receive fields
            'return_pcs': 0,
            'return_gw': 0,
            'return_ct': 0,
            'broken_pcs': 0,
            'broken_gw': 0,
            'broken_ct': 0,
            'loss_pcs': 0,
            'loss_gw': 0,
            'loss_ct': 0,
            'remaining_value': 0,  # Placeholder for value used in jewellery
            'weighted_avg_rate': 0  # Placeholder for weighted average rate
        }

        # If there's corresponding data in stone receive, merge it
        if pckt_no in stone_receive_dict:
            recv_data = stone_receive_dict[pckt_no]
            combined_entry.update({
                'return_pcs': recv_data.get('return_pcs', 0),
                'return_gw': recv_data.get('return_gw', 0),
                'return_ct': recv_data.get('return_ct', 0),
                'broken_pcs': recv_data.get('broken_pcs', 0),
                'broken_gw': recv_data.get('broken_gw', 0),
                'broken_ct': recv_data.get('broken_ct', 0),
                'loss_pcs': recv_data.get('loss_pcs', 0),
                'loss_gw': recv_data.get('loss_gw', 0),
                'loss_ct': recv_data.get('loss_ct', 0),
            })
        
        # Calculate issue and receive weight/quantity values based on UOM
        issue_weight = issue_data.get(uom, 0)
        receive_weight = (
            recv_data.get(f'return_{uom}', 0) + recv_data.get(f'broken_{uom}', 0) + recv_data.get(f'loss_{uom}', 0)
            if pckt_no in stone_receive_dict else 0
        )

        # Calculate weighted average value and rate
        issue_value = issue_weight * issue_data.get('packet__rate_for_retail', 0)
        receive_value = receive_weight * recv_data.get('packet__rate_for_retail', 0) if pckt_no in stone_receive_dict else 0
        remaining_value = issue_value - receive_value
        remaining_wt = issue_weight - receive_weight

        itm_value = itm_value + remaining_value
        


        # Ensure total weight is not zero before dividing
        if remaining_wt != 0:
            weighted_avg_rate = remaining_value / remaining_wt
        else:
            weighted_avg_rate = 0

        combined_entry.update({
            'remaining_value': remaining_value,
            'weighted_avg_rate': weighted_avg_rate
        })

        # Add the combined entry to the final list
        combined_data.append(combined_entry)
    
    # Initialize nw variable
    nw = Decimal('0.0')

    # Calculate the net weight (nw) using the combined data
    for entry in combined_data:
        issue_ct = entry.get('ct', 0)
        return_ct = entry.get('return_ct', 0)
        broken_ct = entry.get('broken_ct', 0)
        loss_ct = entry.get('loss_ct', 0)

        # Perform the net weight calculation
        nw += Decimal(po_item.approx_wt) - (issue_ct / Decimal('5.0')) + ((return_ct + broken_ct + loss_ct) / Decimal('5.0'))
    
    # Prepare the data to be sent as JSON
    data = {
        'item_id': po_item.item.id,
        'short_code': po_item.item.short_code,
        'item_name': po_item.item.item_name,
        'purity_id': po_item.purity.id,
        'purity': po_item.purity.purity,
        'cgst': po_item.item.hsn_no.cgst,
        'sgst': po_item.item.hsn_no.sgst,
        'igst': po_item.item.hsn_no.igst,
        'pcs': po_item.pcs,
        'approx_wt': po_item.approx_wt,
        'gw': sum((Decimal(entry.get('ct', 0)) - Decimal(entry.get('return_ct', 0)) - Decimal(entry.get('broken_ct', 0)) - Decimal(entry.get('loss_ct', 0))) / Decimal('5.0') + (Decimal(entry.get('gw', 0)) - Decimal(entry.get('return_gw', 0)) - Decimal(entry.get('broken_gw', 0)) - Decimal(entry.get('loss_gw', 0))) for entry in combined_data),
        'itm_value' : itm_value,
        'nw': nw,
        'design_code': po_item.design_code,
        'stone_data': combined_data  # Single combined list of stone issue and receive data
    }

    return JsonResponse(data)