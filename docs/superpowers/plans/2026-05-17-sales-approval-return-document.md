# SalesApprovalReturn Document — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full SalesApprovalReturn (SAR) document type — a standalone return voucher (three item entry modes: linked approval, barcode scan, manual) that restores barcodes to stock and marks approval items as returned on save.

**Architecture:** Three-model Django hierarchy (`SalesApprovalReturn → SalesApprovalReturnItem → SalesApprovalReturnItemDetails`) mirroring the SalesApproval structure. SAR prefix in the shared bill-number sequence system. No accounting journal entries — stock/inventory only. Frontend mirrors the SalesApprovalList/Add pattern.

**Tech Stack:** Django 4 + DRF nested serializers, React + React Hook Form + `useFieldArray`, TanStack DataTable, Shadcn/UI components, lucide-react icons.

---

## File Map

| Action | File |
|--------|------|
| Modify | `backend/sales/models.py` — 3 new models at end of file |
| Create | `backend/sales/migrations/0008_sales_approval_return.py` — via makemigrations |
| Modify | `backend/accounting/utils.py` — SAR entry in `_bootstrap_sequence_number` |
| Modify | `backend/sales/serializers.py` — 3 new serializers + updated import |
| Modify | `backend/sales/views/invoice.py` — `SalesApprovalReturnViewset` + `get_next_sar_no` |
| Modify | `backend/inventory/views.py` — `get_barcode_for_return` view |
| Modify | `backend/inventory/urls.py` — register barcode return lookup |
| Modify | `backend/sales/urls.py` — register viewset + next_sar_no endpoint |
| Modify | `frontend/src/services/api/sales.js` — 6 new API functions |
| Modify | `frontend/src/services/api/inventory.js` — `fetchBarcodeForReturn` |
| Create | `frontend/src/components/Sales/SalesApprovalReturnList.jsx` |
| Create | `frontend/src/components/Sales/SalesApprovalReturnAdd.jsx` |
| Modify | `frontend/src/App.jsx` — lazy imports + 3 routes |
| Modify | `frontend/src/config/navData.js` — "Approval Return" nav entry |

---

## Task 1: Backend Models

**Files:**
- Modify: `backend/sales/models.py` (end of file, after `SalesApprovalItemDetails` at line ~541)
- Create: `backend/sales/migrations/0008_sales_approval_return.py` (via makemigrations)

- [ ] **Step 1: Add 3 models to `backend/sales/models.py`**

Append after the closing line of `SalesApprovalItemDetails` (after line 541):

```python
class SalesApprovalReturn(models.Model):
    billno = models.CharField(max_length=30)
    date1 = models.DateField()
    ref_approval = models.ForeignKey(
        SalesApproval, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='returns',
    )
    narration = models.CharField(max_length=100, blank=True, default='')
    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True,
    )
    fiscal_year = models.ForeignKey(
        "mastersconfig.FiscalYearMaster", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = "sales_vou_appr_return"


class SalesApprovalReturnItem(models.Model):
    billno = models.ForeignKey(
        SalesApprovalReturn, on_delete=models.CASCADE, related_name='items',
    )
    barcode = models.ForeignKey(
        BarcodeMain, on_delete=models.PROTECT, null=True, blank=True,
    )
    approval_item = models.ForeignKey(
        SalesApprovalItem, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='return_items',
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    gw = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.CharField(max_length=10, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = "sales_vou_appr_return_main"


class SalesApprovalReturnItemDetails(models.Model):
    billno = models.ForeignKey(
        SalesApprovalReturn, on_delete=models.CASCADE, null=True, blank=True,
    )
    main_item = models.ForeignKey(
        SalesApprovalReturnItem, on_delete=models.CASCADE, related_name='main_item_set',
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    pcs = models.IntegerField()
    ct = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    gw = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, default=0)
    metal_purity = models.CharField(max_length=10, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    packet = models.ForeignKey(
        "mastersconfig.Packet", on_delete=models.SET_NULL, null=True,
    )
    retail = models.ForeignKey(
        "mastersconfig.RetailMaster", on_delete=models.SET_NULL, null=True, blank=True,
    )

    class Meta:
        db_table = "sales_vou_appr_return_detail"
```

- [ ] **Step 2: Generate and apply migration**

Run from `backend/`:
```bash
python manage.py makemigrations sales --name sales_approval_return
python manage.py migrate
```

Expected: `0008_sales_approval_return.py` created and applied with `OK`.

- [ ] **Step 3: Verify with Django check**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add backend/sales/models.py backend/sales/migrations/0008_sales_approval_return.py
git commit -m "feat(sales): add SalesApprovalReturn, SalesApprovalReturnItem, SalesApprovalReturnItemDetails models"
```

---

## Task 2: Register SAR in Bill Number Map

**Files:**
- Modify: `backend/accounting/utils.py` (lines 128–150)

- [ ] **Step 1: Update the import inside `_bootstrap_sequence_number` and add SAR entry**

In `backend/accounting/utils.py`, find the `_bootstrap_sequence_number` function (line ~125). Change the sales models import from:

```python
    from sales.models import SalesVou, SaleReturn, SalesApproval
```

to:

```python
    from sales.models import SalesVou, SaleReturn, SalesApproval, SalesApprovalReturn
```

Then in `model_map_resolved` (lines 135–150), add `'SAR'` after the `'SA'` entry:

```python
        'SA': (SalesApproval, 'billno'),
        'SAR': (SalesApprovalReturn, 'billno'),
```

- [ ] **Step 2: Verify server starts cleanly**

```bash
python manage.py check
```

Expected: no issues.

- [ ] **Step 3: Commit**

```bash
git add backend/accounting/utils.py
git commit -m "feat(accounting): register SAR prefix in bill number sequence map"
```

---

## Task 3: Serializers

**Files:**
- Modify: `backend/sales/serializers.py`

The existing import at line ~403 is:
```python
from sales.models import BankDetail, SalesVou, SalesVouItem, SalesVouItemDetails, SaleReturn, SaleReturnItem, SaleReturnDetails, SalesApproval, SalesApprovalItem, SalesApprovalItemDetails, SaleOldGoldAdjustment
```

- [ ] **Step 1: Extend the sales models import to include the 3 new models**

Change the import at ~line 403 to:

```python
from sales.models import (
    BankDetail, SalesVou, SalesVouItem, SalesVouItemDetails,
    SaleReturn, SaleReturnItem, SaleReturnDetails,
    SalesApproval, SalesApprovalItem, SalesApprovalItemDetails,
    SalesApprovalReturn, SalesApprovalReturnItem, SalesApprovalReturnItemDetails,
    SaleOldGoldAdjustment,
)
```

- [ ] **Step 2: Add 3 serializers after `SalesApprovalSerializer` (after line ~2110)**

Append after the closing of `SalesApprovalSerializer.update()`:

```python
# ── Sales Approval Return serializers ─────────────────────────────────────────

class SalesApprovalReturnItemDetailsSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    packet = serializers.SlugRelatedField(
        queryset=Packet.objects.all(), slug_field="pckt_no", allow_null=True,
    )
    ct = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True, default=0,
    )
    gw = serializers.DecimalField(
        max_digits=10, decimal_places=3, required=False, allow_null=True, default=0,
    )

    class Meta:
        model = SalesApprovalReturnItemDetails
        fields = ['id', 'item', 'pcs', 'ct', 'gw', 'metal_purity', 'rate', 'amount', 'packet']
        extra_kwargs = {'id': {'read_only': False, 'required': False}}
        validators = []


class SalesApprovalReturnItemSerializer(serializers.ModelSerializer):
    item = serializers.SlugRelatedField(queryset=Item.objects.all(), slug_field="short_code")
    barcode = serializers.SlugRelatedField(
        queryset=BarcodeMain.objects.all(), slug_field="barcode",
        allow_null=True, required=False,
    )
    approval_item = serializers.PrimaryKeyRelatedField(
        queryset=SalesApprovalItem.objects.all(), allow_null=True, required=False,
    )
    purity = serializers.CharField(allow_blank=True, allow_null=True, required=False, default='')
    main_item_set = SalesApprovalReturnItemDetailsSerializer(many=True)

    class Meta:
        model = SalesApprovalReturnItem
        fields = [
            'id', 'barcode', 'approval_item', 'item', 'pcs', 'gw', 'purity', 'amount',
            'main_item_set',
        ]
        extra_kwargs = {'id': {'read_only': False, 'required': False}}
        validators = []


class SalesApprovalReturnSerializer(serializers.ModelSerializer):
    ref_approval = serializers.PrimaryKeyRelatedField(
        queryset=SalesApproval.objects.all(), allow_null=True, required=False,
    )
    items = SalesApprovalReturnItemSerializer(many=True)

    class Meta:
        model = SalesApprovalReturn
        fields = [
            'id', 'billno', 'date1', 'ref_approval', 'narration',
            'retail', 'fiscal_year', 'items',
        ]
        extra_kwargs = {
            'id': {'read_only': False, 'required': False},
            'billno': {'read_only': True},
        }

    def create(self, validated_data):
        from accounting.utils import get_next_bill_number
        with transaction.atomic():
            items_data = validated_data.pop('items')
            request = self.context.get('request')
            validated_data['billno'] = get_next_bill_number(
                request.retail, 'SAR', request.retail.active_fy,
            )
            sar = SalesApprovalReturn.objects.create(**validated_data)

            barcode_ids = []
            approval_item_ids = []
            for item in items_data:
                details_data = item.pop('main_item_set')
                sar_item = SalesApprovalReturnItem.objects.create(billno=sar, **item)
                for detail in details_data:
                    SalesApprovalReturnItemDetails.objects.create(
                        billno=sar, main_item=sar_item, **detail,
                    )
                if sar_item.barcode_id:
                    barcode_ids.append(sar_item.barcode_id)
                if sar_item.approval_item_id:
                    approval_item_ids.append(sar_item.approval_item_id)

            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)
            if approval_item_ids:
                SalesApprovalItem.objects.filter(id__in=approval_item_ids).update(ret_status=True)

            return sar

    def update(self, instance, validated_data):
        with transaction.atomic():
            items_data = validated_data.pop('items', [])
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            create_or_update_nested(
                SalesApprovalReturnItemSerializer, instance, 'items', 'billno',
                SalesApprovalReturnItemSerializer(items_data, many=True).data,
            )
            # Reconcile stock and ret_status for all post-update items
            current_items = list(instance.items.all())
            barcode_ids = [it.barcode_id for it in current_items if it.barcode_id]
            approval_item_ids = [it.approval_item_id for it in current_items if it.approval_item_id]
            if barcode_ids:
                BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)
            if approval_item_ids:
                SalesApprovalItem.objects.filter(id__in=approval_item_ids).update(ret_status=True)
            return instance
```

- [ ] **Step 3: Verify import + check**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add backend/sales/serializers.py
git commit -m "feat(sales): add SalesApprovalReturn serializers (3-level nested)"
```

---

## Task 4: Backend Views — Viewset, next_sar_no, Barcode Return Lookup

**Files:**
- Modify: `backend/sales/views/invoice.py`
- Modify: `backend/inventory/views.py`

### 4a — SalesApprovalReturnViewset + get_next_sar_no

- [ ] **Step 1: Add `SalesApprovalReturnSerializer` to the import at line 29**

Line 29 currently reads:
```python
from ..serializers import SalesApprovalSerializer, SalesVouSerializer
```

Change to:
```python
from ..serializers import SalesApprovalSerializer, SalesVouSerializer, SalesApprovalReturnSerializer
```

- [ ] **Step 2: Add the viewset and view after `get_next_sa_no` (after line ~962)**

Insert after `get_next_sa_no`:

```python
class SalesApprovalReturnViewset(views.RetailBaseViewset):
    queryset = SalesApprovalReturn.objects.select_related(
        'ref_approval', 'retail',
    ).prefetch_related(
        'items__main_item_set',
    ).all()
    serializer_class = SalesApprovalReturnSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    search_fields = ['billno', 'ref_approval__billno']
    ordering = ['-date1', '-id']

    @property
    def ordering_fields(self):
        return self.serializer_class.Meta.fields

    def perform_destroy(self, instance):
        from accounting.utils import release_last_bill_number
        retail = instance.retail
        fiscal_year = instance.fiscal_year
        billno = instance.billno
        super().perform_destroy(instance)
        release_last_bill_number(retail, 'SAR', billno, fiscal_year)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_next_sar_no(request):
    from accounting.utils import peek_next_bill_number
    if not request.retail:
        return Response(
            {"error": "Missing or invalid X-RETAIL-ID header"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    bill_no = peek_next_bill_number(request.retail, "SAR")
    return Response({"billno": bill_no})
```

### 4b — Barcode return lookup (inventory)

The existing `get_barcode_only` endpoint at `/inventory/api/get-barcode-detail/<barcode>/` only returns barcodes with `stk_status=True`. For SAR barcode scans, the item is currently OUT (stk_status=False), so we need a separate lookup.

- [ ] **Step 3: Add `get_barcode_for_return` to `backend/inventory/views.py`**

Find `get_barcode_only` (line ~75) and add the following immediately after it:

```python
@api_view()
@permission_classes([IsAuthenticated])
def get_barcode_for_return(request, barcode):
    """
    Look up a barcode for use in a SalesApprovalReturn form.
    Unlike get_barcode_only, this does NOT filter by stk_status — the
    barcode being returned is currently OUT (stk_status=False).
    """
    try:
        obj = BarcodeMain.objects.select_related(
            'item', 'purity',
        ).prefetch_related('barcodedetails_set__item').get(
            barcode=barcode,
            retail=request.retail,
        )
    except BarcodeMain.DoesNotExist:
        return Response(
            {"detail": f"Barcode '{barcode}' not found in the current retail."},
            status=404,
        )
    data = BarcodeMainToSaleVouSerializer(obj).data
    return Response(data)
```

- [ ] **Step 4: Verify check passes**

```bash
python manage.py check
```

Expected: no issues.

- [ ] **Step 5: Commit**

```bash
git add backend/sales/views/invoice.py backend/inventory/views.py
git commit -m "feat(sales): add SalesApprovalReturnViewset, get_next_sar_no, get_barcode_for_return"
```

---

## Task 5: URL Routes

**Files:**
- Modify: `backend/sales/urls.py`
- Modify: `backend/inventory/urls.py`

- [ ] **Step 1: Register SAR viewset and next_sar_no in `backend/sales/urls.py`**

Add the router registration after `sale-approval`:
```python
router.register(r'sale-approval-return', views.SalesApprovalReturnViewset)
```

Add the URL path after `path('api/next_sa_no', views.get_next_sa_no),`:
```python
path('api/next_sar_no', views.get_next_sar_no),
```

- [ ] **Step 2: Register barcode return lookup in `backend/inventory/urls.py`**

Find line 36 (`path('api/get-barcode-detail/<str:barcode>/', views.get_barcode_only)`).

Add after it:
```python
path('api/get-barcode-for-return/<str:barcode>/', views.get_barcode_for_return),
```

- [ ] **Step 3: Smoke-test both endpoints**

Start the dev server (`python manage.py runserver`) and with a valid retail header:
- `GET /sales/api/sale-approval-return/` → `{"count": 0, "results": []}`
- `GET /sales/api/next_sar_no` → `{"billno": "SAR-00001"}` (or your prefix format)

- [ ] **Step 4: Commit**

```bash
git add backend/sales/urls.py backend/inventory/urls.py
git commit -m "feat(sales): register sale-approval-return routes and get_barcode_for_return URL"
```

---

## Task 6: Frontend API Service Functions

**Files:**
- Modify: `frontend/src/services/api/sales.js`
- Modify: `frontend/src/services/api/inventory.js`

- [ ] **Step 1: Add 6 SAR functions to `frontend/src/services/api/sales.js`**

Append after `fetchNextSaleAppNo` (after line ~45):

```js
export async function fetchNextSARNo() {
  try {
    const response = await apiClient.get(`/sales/api/next_sar_no`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchNextSARNo:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalReturns({ search = "", page = 1, ordering = "" } = {}) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval-return/`, {
      params: { search, page, ordering },
    });
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchSalesApprovalReturns:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function fetchSalesApprovalReturnById(id) {
  try {
    const response = await apiClient.get(`/sales/api/sale-approval-return/${id}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchSalesApprovalReturnById:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function createSalesApprovalReturn(data) {
  try {
    const response = await apiClient.post(`/sales/api/sale-approval-return/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("createSalesApprovalReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function updateSalesApprovalReturn(data, id) {
  try {
    const response = await apiClient.put(`/sales/api/sale-approval-return/${id}/`, data);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("updateSalesApprovalReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}

export async function deleteSalesApprovalReturn(id, toast) {
  return handleDelete(`/sales/api/sale-approval-return/${id}/`, toast);
}
```

- [ ] **Step 2: Add `fetchBarcodeForReturn` to `frontend/src/services/api/inventory.js`**

Append after `fetchBarcodeDetailOnly`:

```js
export async function fetchBarcodeForReturn(barcode) {
  try {
    if (!barcode) return { success: false, error: "Barcode cannot be blank" };
    const response = await apiClient.get(`/inventory/api/get-barcode-for-return/${barcode}/`);
    return { success: true, data: response.data };
  } catch (error) {
    console.error("fetchBarcodeForReturn:", error.response?.data || error.message);
    return { success: false, error: error.response?.data || error.message };
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/services/api/sales.js frontend/src/services/api/inventory.js
git commit -m "feat(frontend): add SAR API functions and fetchBarcodeForReturn"
```

---

## Task 7: SalesApprovalReturnList.jsx

**Files:**
- Create: `frontend/src/components/Sales/SalesApprovalReturnList.jsx`

Mirrors `SalesApprovalList.jsx` but with SAR-specific columns and no inline return sheet.

- [ ] **Step 1: Create the file**

```jsx
// frontend/src/components/Sales/SalesApprovalReturnList.jsx
import { useState, useEffect, useCallback } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';
import {
  fetchSalesApprovalReturns,
  deleteSalesApprovalReturn,
} from '../../services/apiService';

function SalesApprovalReturnList() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  const fetchList = useCallback(async () => {
    setLoading(true);
    const result = await fetchSalesApprovalReturns({ search, page, ordering: sortby });
    if (result.success) {
      setRecords(result.data.results);
      setTotalPages(result.data.total_pages);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [search, page, sortby]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleDelete = async (id) => {
    await deleteSalesApprovalReturn(id, toast);
    fetchList();
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-2">
          <Link
            to={`/sales/salesapprovalreturn/${row.original.id}`}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
          >
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => handleDelete(row.original.id)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) =>
        new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
    { header: "Bill No", accessorKey: "billno" },
    {
      header: "Ref Approval",
      accessorKey: "ref_approval",
      cell: ({ getValue }) => getValue() ?? "—",
    },
    {
      header: "Items",
      accessorKey: "items",
      cell: ({ getValue }) => (getValue() || []).length,
    },
    { header: "Narration", accessorKey: "narration" },
  ];

  return (
    <div className="p-4">
      <div className="flex justify-between mb-4">
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({ search: e.target.value, sortby })}
          placeholder="Search bill no or ref approval…"
          className="max-w-sm"
        />
        <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
          <SelectTrigger className="max-w-sm">
            <span>Sort By</span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="date1">(Old) Date</SelectItem>
            <SelectItem value="-date1">(New) Date</SelectItem>
            <SelectItem value="billno">(Asc) Bill No</SelectItem>
            <SelectItem value="-billno">(Desc) Bill No</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {loading ? (
        <div>{[...Array(4)].map((_, i) => <Skeleton key={i} className="w-full h-8 mb-2" />)}</div>
      ) : error ? (
        <div className="text-red-500">Error: {error}</div>
      ) : (
        <>
          <DataTable columns={columns} data={records} />

          <div className="flex justify-between items-center mt-4">
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span>Page {page} of {totalPages}</span>
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>

          <div className="flex justify-end mt-4">
            <Link to="/sales/salesapprovalreturn/add/">
              <Button>Add New</Button>
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

export default SalesApprovalReturnList;
```

- [ ] **Step 2: Verify page loads at `/sales/salesapprovalreturn/list/` (after routes are added in Task 9)**

Empty table should render with no errors in the console.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sales/SalesApprovalReturnList.jsx
git commit -m "feat(frontend): add SalesApprovalReturnList page"
```

---

## Task 8: SalesApprovalReturnAdd.jsx

**Files:**
- Create: `frontend/src/components/Sales/SalesApprovalReturnAdd.jsx`

This is the main add/edit form with three item entry modes.

**Response format note:** `fetchBarcodeForReturn(barcode)` uses `BarcodeMainToSaleVouSerializer`, which returns:
- Top-level: `barcode` (string), `item` (short_code), `purity` (string e.g. "18K"), `pcs`, `gw`
- Sub-items: `main_item_set` array, each with `item` (short_code), `pcs`, `ct`, `gw`, `metal_purity`, `rate`, `amt` (note: `amt` not `amount`)

When mapping barcode scan response to form item, use `d.amt || d.amount || 0` for sub-item amounts.

- [ ] **Step 1: Create the file**

```jsx
// frontend/src/components/Sales/SalesApprovalReturnAdd.jsx
import React, { useEffect, useState, useRef } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { renderErrorTree } from "../../Utils";
import { useParams, useNavigate } from "react-router-dom";
import { ChevronDown, ChevronRight, Trash2, Plus } from "lucide-react";
import {
  Table,
  TableRow,
  TableCell,
  TableBody,
  TableHead,
  TableHeader,
} from "@/components/ui/table";
import {
  fetchNextSARNo,
  fetchSalesApprovalReturnById,
  createSalesApprovalReturn,
  updateSalesApprovalReturn,
  fetchSalesApproval,
  fetchSalesApprovalById,
  fetchBarcodeForReturn,
  fetchPackets,
  fetchMainItem,
} from "@/services/apiService";

const today = new Date().toISOString().split("T")[0];

const SalesApprovalReturnAdd = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const { register, handleSubmit, control, setValue, getValues, watch } = useForm({
    defaultValues: {
      date1: today,
      billno: "",
      ref_approval: null,
      narration: "",
      items: [],
      _barcode: "",
      _refSearch: "",
    },
  });

  const { fields, append, remove, update } = useFieldArray({ control, name: "items" });

  const [saving, setSaving] = useState(false);
  const [packets, setPackets] = useState([]);
  const [mainItems, setMainItems] = useState([]);
  const [approvalResults, setApprovalResults] = useState([]);
  const [selectedApproval, setSelectedApproval] = useState(null);
  const [expandedRows, setExpandedRows] = useState({});
  const refSearchDebounce = useRef(null);

  /* ── Initial data load ── */
  useEffect(() => {
    async function init() {
      const [packetsRes, mainItemRes, billNoRes] = await Promise.all([
        fetchPackets(),
        fetchMainItem(),
        id ? Promise.resolve({ success: false }) : fetchNextSARNo(),
      ]);
      if (packetsRes.success) setPackets(packetsRes.data.results ?? packetsRes.data);
      if (mainItemRes.success) setMainItems(mainItemRes.data.results ?? mainItemRes.data);
      if (billNoRes.success) setValue("billno", billNoRes.data.billno);

      if (id) {
        const res = await fetchSalesApprovalReturnById(id);
        if (res.success) {
          const d = res.data;
          setValue("date1", d.date1);
          setValue("billno", d.billno);
          setValue("ref_approval", d.ref_approval ?? null);
          setValue("narration", d.narration ?? "");
          (d.items || []).forEach((item) => append(item));
          // Restore approval preview if ref is set
          if (d.ref_approval) {
            const aRes = await fetchSalesApprovalById(d.ref_approval);
            if (aRes.success) setSelectedApproval(aRes.data);
          }
        }
      }
    }
    init();
  }, []);

  /* ── Ref approval search (debounced 300 ms) ── */
  const refSearch = watch("_refSearch");
  useEffect(() => {
    clearTimeout(refSearchDebounce.current);
    if (!refSearch || refSearch.length < 2) {
      setApprovalResults([]);
      return;
    }
    refSearchDebounce.current = setTimeout(async () => {
      const res = await fetchSalesApproval({ search: refSearch, page: 1 });
      if (res.success) setApprovalResults(res.data.results || []);
    }, 300);
    return () => clearTimeout(refSearchDebounce.current);
  }, [refSearch]);

  const handleSelectApproval = async (approval) => {
    setApprovalResults([]);
    setValue("_refSearch", approval.billno);
    setValue("ref_approval", approval.id);
    const res = await fetchSalesApprovalById(approval.id);
    if (res.success) setSelectedApproval(res.data);
  };

  const clearApproval = () => {
    setSelectedApproval(null);
    setValue("_refSearch", "");
    setValue("ref_approval", null);
    // Remove all items that came from this approval
    const toRemove = fields
      .map((f, i) => (f.approval_item ? i : null))
      .filter((i) => i !== null)
      .reverse();
    toRemove.forEach((i) => remove(i));
  };

  /* ── Toggle approval item checkbox ── */
  const isApprovalItemChecked = (approvalItemId) =>
    fields.some((f) => f.approval_item === approvalItemId);

  const toggleApprovalItem = (approvalItem) => {
    const idx = fields.findIndex((f) => f.approval_item === approvalItem.id);
    if (idx >= 0) {
      remove(idx);
    } else {
      append({
        barcode: approvalItem.barcode ?? null,
        approval_item: approvalItem.id,
        item: approvalItem.item,
        pcs: approvalItem.pcs,
        gw: approvalItem.gw,
        purity: approvalItem.purity ?? "",
        amount: approvalItem.amount ?? 0,
        main_item_set: (approvalItem.main_item_set || []).map((d) => ({
          item: d.item,
          pcs: d.pcs,
          ct: d.ct ?? null,
          gw: d.gw ?? null,
          metal_purity: d.metal_purity ?? "",
          rate: d.rate,
          amount: d.amount ?? d.amt ?? 0,
          packet: d.packet ?? null,
        })),
      });
    }
  };

  /* ── Barcode scan ── */
  const handleBarcodeBlur = async () => {
    const bc = getValues("_barcode");
    if (!bc) return;
    const res = await fetchBarcodeForReturn(bc);
    if (res.success) {
      const d = res.data;
      append({
        barcode: d.barcode,
        approval_item: null,
        item: d.item,
        pcs: d.pcs ?? 1,
        gw: d.gw ?? 0,
        purity: d.purity ?? "",
        amount: d.amount ?? 0,
        main_item_set: (d.main_item_set || []).map((sub) => ({
          item: sub.item,
          pcs: sub.pcs ?? 1,
          ct: sub.ct ?? null,
          gw: sub.gw ?? null,
          metal_purity: sub.metal_purity ?? "",
          rate: sub.rate ?? 0,
          amount: sub.amount ?? sub.amt ?? 0,
          packet: sub.packet ?? null,
        })),
      });
      setValue("_barcode", "");
    } else {
      toast({
        title: "Barcode not found",
        description: res.error?.detail ?? String(bc),
        variant: "destructive",
      });
    }
  };

  /* ── Manual add row ── */
  const addManualRow = () => {
    append({
      barcode: null,
      approval_item: null,
      item: "",
      pcs: 1,
      gw: 0,
      purity: "",
      amount: 0,
      main_item_set: [],
    });
  };

  /* ── Add sub-item row to a main item ── */
  const addSubRow = (mainIdx) => {
    const current = getValues(`items.${mainIdx}.main_item_set`) || [];
    setValue(`items.${mainIdx}.main_item_set`, [
      ...current,
      { item: "", pcs: 1, ct: null, gw: null, metal_purity: "", rate: 0, amount: 0, packet: null },
    ]);
  };

  const removeSubRow = (mainIdx, subIdx) => {
    const current = getValues(`items.${mainIdx}.main_item_set`) || [];
    setValue(
      `items.${mainIdx}.main_item_set`,
      current.filter((_, i) => i !== subIdx),
    );
  };

  /* ── Submit ── */
  const onSubmit = async (formData) => {
    if (fields.length === 0) {
      toast({ title: "No items", description: "Add at least one return item.", variant: "destructive" });
      return;
    }
    const payload = {
      date1: formData.date1,
      ref_approval: formData.ref_approval ?? null,
      narration: formData.narration ?? "",
      items: fields.map((item) => ({
        ...(item.id ? { id: item.id } : {}),
        barcode: item.barcode ?? null,
        approval_item: item.approval_item ?? null,
        item: item.item,
        pcs: Number(item.pcs),
        gw: item.gw,
        purity: item.purity ?? "",
        amount: item.amount ?? 0,
        main_item_set: (item.main_item_set || []).map((d) => ({
          ...(d.id ? { id: d.id } : {}),
          item: d.item,
          pcs: Number(d.pcs),
          ct: d.ct ?? null,
          gw: d.gw ?? null,
          metal_purity: d.metal_purity ?? null,
          rate: d.rate,
          amount: d.amount,
          packet: d.packet ?? null,
        })),
      })),
    };

    setSaving(true);
    const result = id
      ? await updateSalesApprovalReturn(payload, id)
      : await createSalesApprovalReturn(payload);
    setSaving(false);

    if (result.success) {
      toast({ title: id ? "Updated" : "Saved", description: `Return ${result.data.billno} recorded.` });
      navigate("/sales/salesapprovalreturn/list/");
    } else {
      toast({
        title: "Error saving",
        description: renderErrorTree(result.error),
        variant: "destructive",
      });
    }
  };

  useF4Submit(handleSubmit(onSubmit));

  const toggleExpand = (idx) =>
    setExpandedRows((prev) => ({ ...prev, [idx]: !prev[idx] }));

  return (
    <div className="p-4 max-w-5xl mx-auto space-y-6">
      {/* ── Header section ── */}
      <form onSubmit={handleSubmit(onSubmit)}>
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div>
            <Label>Bill No</Label>
            <Input {...register("billno")} readOnly className="bg-muted" />
          </div>
          <div>
            <Label>Date</Label>
            <Input type="date" {...register("date1")} />
          </div>
          <div className="col-span-2 relative">
            <Label>Reference Approval (optional)</Label>
            <div className="flex gap-2">
              <Input
                {...register("_refSearch")}
                placeholder="Search by approval bill no…"
                autoComplete="off"
              />
              {selectedApproval && (
                <Button type="button" variant="outline" size="sm" onClick={clearApproval}>
                  Clear
                </Button>
              )}
            </div>
            {approvalResults.length > 0 && (
              <div className="absolute z-10 mt-1 bg-white border rounded shadow w-full max-h-48 overflow-y-auto">
                {approvalResults.map((a) => (
                  <div
                    key={a.id}
                    className="px-3 py-2 hover:bg-gray-100 cursor-pointer text-sm"
                    onClick={() => handleSelectApproval(a)}
                  >
                    {a.billno} — {a.ldgr_name}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="col-span-2">
            <Label>Narration</Label>
            <Input {...register("narration")} placeholder="Optional notes" />
          </div>
        </div>

        {/* ── From linked approval: checkbox list ── */}
        {selectedApproval && (
          <div className="border rounded p-3 mb-4 bg-slate-50">
            <p className="text-sm font-semibold mb-2 text-slate-700">
              Items from {selectedApproval.billno} — tick to include in return:
            </p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8">✓</TableHead>
                  <TableHead>Barcode</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>GW</TableHead>
                  <TableHead>Purity</TableHead>
                  <TableHead>Amount</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(selectedApproval.items || []).map((ai) => (
                  <TableRow
                    key={ai.id}
                    className={ai.ret_status ? "opacity-40" : ""}
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        checked={isApprovalItemChecked(ai.id)}
                        disabled={ai.ret_status}
                        onChange={() => toggleApprovalItem(ai)}
                      />
                    </TableCell>
                    <TableCell className="text-xs">{ai.barcode}</TableCell>
                    <TableCell className="text-xs">{ai.item}</TableCell>
                    <TableCell className="text-xs">{ai.gw}</TableCell>
                    <TableCell className="text-xs">{ai.purity}</TableCell>
                    <TableCell className="text-xs">
                      {Number(ai.amount || 0).toLocaleString("en-IN", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* ── Barcode scan ── */}
        <div className="flex gap-2 mb-4 items-end">
          <div className="flex-1">
            <Label>Scan Barcode</Label>
            <Input
              {...register("_barcode")}
              placeholder="Scan or type barcode then Tab/click away…"
              onBlur={handleBarcodeBlur}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleBarcodeBlur())}
            />
          </div>
          <Button type="button" variant="outline" onClick={addManualRow}>
            <Plus className="size-4 mr-1" /> Add Row
          </Button>
        </div>

        {/* ── Items table ── */}
        {fields.length > 0 && (
          <div className="border rounded mb-4 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Barcode</TableHead>
                  <TableHead>Item</TableHead>
                  <TableHead>Pcs</TableHead>
                  <TableHead>GW</TableHead>
                  <TableHead>Purity</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {fields.map((field, idx) => (
                  <React.Fragment key={field.id}>
                    <TableRow>
                      <TableCell>
                        <button
                          type="button"
                          onClick={() => toggleExpand(idx)}
                          className="text-slate-500"
                        >
                          {expandedRows[idx] ? (
                            <ChevronDown className="size-4" />
                          ) : (
                            <ChevronRight className="size-4" />
                          )}
                        </button>
                      </TableCell>
                      <TableCell className="text-xs">{field.barcode ?? "—"}</TableCell>
                      <TableCell>
                        <Input
                          {...register(`items.${idx}.item`)}
                          list={`items-datalist-${idx}`}
                          className="h-7 text-xs w-28"
                        />
                        <datalist id={`items-datalist-${idx}`}>
                          {mainItems.map((m) => (
                            <option key={m.id} value={m.short_code}>{m.item_name}</option>
                          ))}
                        </datalist>
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          {...register(`items.${idx}.pcs`)}
                          className="h-7 text-xs w-16"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          step="0.001"
                          {...register(`items.${idx}.gw`)}
                          className="h-7 text-xs w-20"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          {...register(`items.${idx}.purity`)}
                          className="h-7 text-xs w-16"
                          placeholder="18K"
                        />
                      </TableCell>
                      <TableCell>
                        <Input
                          type="number"
                          step="0.01"
                          {...register(`items.${idx}.amount`)}
                          className="h-7 text-xs w-24"
                        />
                      </TableCell>
                      <TableCell>
                        <button
                          type="button"
                          onClick={() => remove(idx)}
                          className="text-red-500 hover:text-red-700"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </TableCell>
                    </TableRow>

                    {/* ── Sub-items (expanded) ── */}
                    {expandedRows[idx] && (
                      <TableRow>
                        <TableCell colSpan={8} className="bg-slate-50 p-2">
                          <Table>
                            <TableHeader>
                              <TableRow>
                                <TableHead>Item</TableHead>
                                <TableHead>Pcs</TableHead>
                                <TableHead>Ct</TableHead>
                                <TableHead>GW</TableHead>
                                <TableHead>Metal Purity</TableHead>
                                <TableHead>Rate</TableHead>
                                <TableHead>Amount</TableHead>
                                <TableHead>Packet</TableHead>
                                <TableHead className="w-8" />
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {(watch(`items.${idx}.main_item_set`) || []).map((sub, si) => (
                                <TableRow key={si}>
                                  <TableCell>
                                    <Input
                                      {...register(`items.${idx}.main_item_set.${si}.item`)}
                                      list={`sub-items-datalist-${idx}-${si}`}
                                      className="h-7 text-xs w-24"
                                    />
                                    <datalist id={`sub-items-datalist-${idx}-${si}`}>
                                      {mainItems.map((m) => (
                                        <option key={m.id} value={m.short_code}>{m.item_name}</option>
                                      ))}
                                    </datalist>
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      type="number"
                                      {...register(`items.${idx}.main_item_set.${si}.pcs`)}
                                      className="h-7 text-xs w-14"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      type="number"
                                      step="0.001"
                                      {...register(`items.${idx}.main_item_set.${si}.ct`)}
                                      className="h-7 text-xs w-16"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      type="number"
                                      step="0.001"
                                      {...register(`items.${idx}.main_item_set.${si}.gw`)}
                                      className="h-7 text-xs w-16"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      {...register(`items.${idx}.main_item_set.${si}.metal_purity`)}
                                      className="h-7 text-xs w-16"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      type="number"
                                      step="0.001"
                                      {...register(`items.${idx}.main_item_set.${si}.rate`)}
                                      className="h-7 text-xs w-20"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Input
                                      type="number"
                                      step="0.01"
                                      {...register(`items.${idx}.main_item_set.${si}.amount`)}
                                      className="h-7 text-xs w-20"
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <select
                                      {...register(`items.${idx}.main_item_set.${si}.packet`)}
                                      className="h-7 text-xs border rounded px-1 w-24"
                                    >
                                      <option value="">—</option>
                                      {packets.map((p) => (
                                        <option key={p.id} value={p.pckt_no}>{p.pckt_no}</option>
                                      ))}
                                    </select>
                                  </TableCell>
                                  <TableCell>
                                    <button
                                      type="button"
                                      onClick={() => removeSubRow(idx, si)}
                                      className="text-red-400 hover:text-red-600"
                                    >
                                      <Trash2 className="size-3" />
                                    </button>
                                  </TableCell>
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="mt-1 text-xs"
                            onClick={() => addSubRow(idx)}
                          >
                            <Plus className="size-3 mr-1" /> Add Sub-item
                          </Button>
                        </TableCell>
                      </TableRow>
                    )}
                  </React.Fragment>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* ── Footer ── */}
        <div className="flex justify-end gap-2 mt-4">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/sales/salesapprovalreturn/list/")}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? "Saving…" : id ? "Update (F4)" : "Save (F4)"}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default SalesApprovalReturnAdd;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Sales/SalesApprovalReturnAdd.jsx
git commit -m "feat(frontend): add SalesApprovalReturnAdd form (3 entry modes)"
```

---

## Task 9: App.jsx Routes + navData.js Navbar

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/config/navData.js`

- [ ] **Step 1: Add lazy imports to `App.jsx`**

Find the line (around line 47):
```js
const SalesApprovalReturnPage    = lazy(() => import("./components/Sales/SalesApprovalReturnPage"));
```

Add two lines directly after it:
```js
const SalesApprovalReturnList    = lazy(() => import("./components/Sales/SalesApprovalReturnList"));
const SalesApprovalReturnAdd     = lazy(() => import("./components/Sales/SalesApprovalReturnAdd"));
```

- [ ] **Step 2: Add 3 routes to `App.jsx`**

Find the existing SalesApproval routes block (~line 407–411):
```js
  { path: "sales/salesapproval",           heading: null,                   component: <Navigate to="/sales/salesapproval/list/" replace /> },
  { path: "sales/salesapproval/list/",     heading: "Sales Approval List",  component: <SalesApprovalList /> },
  { path: "sales/salesapproval/add/",      heading: "Add Sales Approval",   component: <SalesApprovalAdd /> },
  { path: "sales/salesapproval/:id/return", heading: "Record Return",       component: <SalesApprovalReturnPage /> },
  { path: "sales/salesapproval/:id",       heading: "Edit Sales Approval",  component: <SalesApprovalAdd /> },
```

Add immediately after this block:
```js
  { path: "sales/salesapprovalreturn/list/", heading: "Approval Return List",   component: <SalesApprovalReturnList /> },
  { path: "sales/salesapprovalreturn/add/",  heading: "Add Approval Return",    component: <SalesApprovalReturnAdd /> },
  { path: "sales/salesapprovalreturn/:id",   heading: "Edit Approval Return",   component: <SalesApprovalReturnAdd /> },
```

- [ ] **Step 3: Add nav entry to `frontend/src/config/navData.js`**

Find the imports at the top of `navData.js` and add `PackageXIcon` if not already imported (it's used by Sales Return). Then find (line ~168–169):

```js
    { title: "Sales Approval", url: "/sales/salesapproval/list/", icon: PackageCheckIcon },
    { title: "E-Way Bills",    url: "/sales/eway-bills",            icon: FileText         },
```

Insert between them:
```js
    { title: "Approval Return", url: "/sales/salesapprovalreturn/list/", icon: PackageXIcon },
```

> **Note:** `PackageXIcon` is already used by Sales Return on line 167, so no new import needed.

- [ ] **Step 4: Verify the full flow in the browser**

1. Navigate to Sales → "Approval Return" in the sidebar → list page loads
2. Click "Add New" → SAR form loads with auto-generated bill no (e.g. `SAR-00001`)
3. Search for an existing Sales Approval in "Reference Approval" → items appear as checkboxes → tick one → row appears in items table
4. Expand a row (ChevronRight) → sub-items show
5. Press F4 → record saves → redirect to list → row appears
6. Click Edit → form loads with saved data
7. Click Delete on list → record removed
8. On the Sales Approval list, verify the ticked item now shows `ret_status: true`
9. On Barcode Management, verify barcode `stk_status` is back to `true`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx frontend/src/config/navData.js
git commit -m "feat(frontend): register SAR routes and add Approval Return to navbar"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Bill no auto-generated with `SAR` prefix, released on delete
- ✅ Optional `ref_approval` FK
- ✅ Three item entry modes: linked approval checkboxes, barcode scan, manual
- ✅ On save: `stk_status=True` for barcoded items, `ret_status=True` for linked approval items
- ✅ Nested `SalesApprovalReturnItemDetails` (sub-item breakdown)
- ✅ F4 save
- ✅ List page: Date, Bill No, Ref Approval, Items count, Edit/Delete
- ✅ Search by billno / ref_approval billno
- ✅ "Approval Return" nav entry between "Sales Approval" and "E-Way Bills"

**Out of scope (explicitly excluded):**
- No accounting journal entries
- No GST on return
- No print receipt
- `ret_status` is one-way (no un-return)
