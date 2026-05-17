import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";
import { fetchSalesApprovalById, returnSalesApprovalItems } from "@/services/api/sales";
import SalesApprovalReturnForm from "./SalesApprovalReturnForm";

export default function SalesApprovalReturnPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [approval, setApproval] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      setLoading(true);
      const res = await fetchSalesApprovalById(id);
      if (res.success) setApproval(res.data);
      else toast({ title: "Failed to load approval", variant: "destructive" });
      setLoading(false);
    })();
  }, [id]);

  const handleSave = async (returnedItemIds) => {
    setSaving(true);
    const res = await returnSalesApprovalItems(id, returnedItemIds);
    setSaving(false);
    if (res.success) {
      toast({ title: "Return recorded successfully" });
      navigate("/sales/salesapproval/list/");
    } else {
      toast({
        title: "Failed to record return",
        description: JSON.stringify(res.error),
        variant: "destructive",
      });
    }
  };

  return (
    <div className="container mt-4 max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate("/sales/salesapproval/list/")}
        >
          <ArrowLeft className="size-4" />
        </Button>
        <h1 className="text-lg font-semibold">Record Approval Return</h1>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Loading…
        </div>
      ) : (
        <SalesApprovalReturnForm
          approval={approval}
          onSave={handleSave}
          saving={saving}
        />
      )}
    </div>
  );
}
