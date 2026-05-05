import React, { useEffect, useState, useRef } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { useF2Navigate } from "@/hooks/useF2Navigate"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder, createJournalEntry, getVoucherAttachments, uploadVoucherAttachment, deleteVoucherAttachment } from "@/services/apiService";
import { Link, useParams, useSearchParams, useNavigate } from "react-router-dom";

// Only these four voucher types are valid for the journal/receipt/payment/contra
// editor. Anything else (e.g. /accounting/AddJournal/JRNL pointing at a legacy
// bookmark) would otherwise render this component with garbage params and
// trigger a cascade of 4xx/5xx API calls.
const VALID_JOURNAL_TYPES = ["JRNL", "RCPT", "PMNT", "CONTRA"];
import { FieldContainer } from "@/Utils";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { fetchAccountingVoucher, fetchJournalEntryForEdit, fetchVoucherNoNext, updateJournalEntryForEdit } from "../../../services/apiService";
import { SquarePen, Trash2, Paperclip, Upload, FileText, X } from "lucide-react";
import AccountSuggestion from "@/components/AI/AccountSuggestion";
import BillAllocationTable from "./BillAllocationTable";
import { useEditDirty } from "@/hooks/useEditDirty";

const AddJournal = () => {
  const { toast } = useToast()
  const navigate = useNavigate();
  const {id} = useParams()
  const { journal_type } = useParams();
  const isValidType = !journal_type || VALID_JOURNAL_TYPES.includes(journal_type);

  const [searchParams] = useSearchParams();
  // Pre-fill linkage from query string when launched from a Customer Order
  // (e.g. .../accounting/RCPT/add?customer_order=12&order_no=CO-1 ).
  const preCustomerOrderId = searchParams.get("customer_order") || "";
  const preOrderNo         = searchParams.get("order_no")       || "";
  const preLedgerName      = searchParams.get("ldgr_name")      || "";
  const { register, handleSubmit, control, reset, watch, setValue, getValues, formState: { isDirty } } = useForm({
    defaultValues: {

      form: {
        date: new Date().toISOString().split("T")[0],

        voucher_type: "",
        customer_order: preCustomerOrderId || null,
      },
      table: { credit: 0, debit: 0 }

    },
  });
  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [allocations, setAllocations] = useState([]);  // bill-wise allocations for current party row
  const [narrationForSuggestion, setNarrationForSuggestion] = useState(null);
  const [saving, setSaving] = useState(false);
  const { canSave, saveLabel, markTableDirty, resetTableDirty } = useEditDirty({ id, isDirty });
  const [savedVoucherId, setSavedVoucherId] = useState(id || null);
  const [savedAttachments, setSavedAttachments] = useState([]);   // already uploaded (edit mode)
  const [pendingFiles, setPendingFiles]         = useState([]);   // queued (add mode, uploaded on save)
  const [uploadingFiles, setUploadingFiles]     = useState(false);
  const [customers, setCustomers] = useState([]);
  const [selectedLedger, setSelectedLedger] = useState(null);
  const [purityData, setPurityData] = useState([]);
  const [totalCredit, settotalCredit] = useState(0);
  const [totalDebit, settotalDebit] = useState(0);

  // Redirect away from malformed URLs (e.g. legacy /accounting/AddJournal/JRNL)
  useEffect(() => {
    if (!isValidType) navigate("/accounting", { replace: true });
  }, [isValidType, navigate]);

  // Load existing attachments when editing
  useEffect(() => {
    if (!isValidType || !id) return;
    if (id) {
      getVoucherAttachments(id).then((res) => {
        if (res.success) {
          const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
          setSavedAttachments(data);
        }
      });
    }
  }, [id]);

  useEffect(() => {
    if (!isValidType) return;
    if (journal_type) {
      setValue("form.voucher_type", journal_type); // Set the default voucher type
    }

    if (id)fetchJournalEntryForEdit(id).then
      ((response) => {
        Object.keys(response.data).forEach((key) => {
          setValue(`form.${key}`, response.data[key]);
        });

        // Set items array
        if (response.data.voucher_details) {
          setRows(response.data.voucher_details);
        }
        reset(getValues(), { keepValues: true, keepDirty: false });
        resetTableDirty();
      })
      .catch((error) => {
        console.error('Error fetching manufacturing issue:', error);
      });
    

  }, [journal_type, setValue]);

  useEffect(() => {
    const totalDebit = rs.reduce((acc, row) => acc + (parseFloat(row.debit) || 0), 0);
    const totalCredit = rs.reduce((acc, row) => acc + (parseFloat(row.credit) || 0), 0);
    settotalDebit(totalDebit);
    settotalCredit(totalCredit);

  }, [rs]);

  useEffect(() => {
    if (!isValidType) return;
    async function fetchData() {
      const [salesperson, orderNo, mainItem, purity] = await Promise.all([
        fetchSalesperson(),
        fetchVoucherNoNext(journal_type),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (salesperson.success) setSalespersonData(salesperson.data.results);
      if (!id && orderNo.success) setValue("form.voucher_no", orderNo.data.billno);
      if (mainItem.success) setMainItemData(mainItem.data.results);
      if (purity.success) setPurityData(purity.data.results);
    }
    fetchData();
  }, []);

  const account_name = watch("table.account");
  const accountTimerRef = useRef(null);
  useEffect(() => {
    if (accountTimerRef.current) clearTimeout(accountTimerRef.current);
    accountTimerRef.current = setTimeout(() => {
      getLedgers({ search: account_name, type: "" }).then(res => {
        if (res.success) setCustomers(res.data.results);
      });
    }, 300);
    return () => clearTimeout(accountTimerRef.current);
  }, [account_name]);

  const onSubmit = (data) => {
    const form = getValues('form')
    form.voucher_details = rs.map(row => ({
      ...row,
      debit:  parseFloat(row.debit)  || 0,
      credit: parseFloat(row.credit) || 0,
    }));

    console.log(form)
    if (rs.length === 0) {
      toast({ title: "Add at least one line item", variant: "destructive" });
      return;
    }
    if (totalDebit === 0 && totalCredit === 0) {
      toast({ title: "Voucher amounts cannot be zero", variant: "destructive" });
      return;
    }
    if (Math.abs(totalCredit - totalDebit) > 0.01) {
      toast({ title: "Debit and Credit should be equal", description: `Difference: ₹${Math.abs(totalCredit - totalDebit).toLocaleString("en-IN")}`, variant: "destructive" });
      return;
    }

    setSaving(true);
    (id ? updateJournalEntryForEdit(form,id) : createJournalEntry(form))
      .then(async (response) => {

        if (response.success) {
          const vId = id || response.data?.id;
          if (!id && vId) setSavedVoucherId(vId);

          // Upload any files that were queued before the voucher existed
          if (pendingFiles.length > 0 && vId) {
            setUploadingFiles(true);
            for (const file of pendingFiles) {
              await uploadVoucherAttachment(vId, file);
            }
            setPendingFiles([]);
            // Refresh saved attachments list
            const attRes = await getVoucherAttachments(vId);
            if (attRes.success) {
              const data = Array.isArray(attRes.data) ? attRes.data : attRes.data?.results ?? [];
              setSavedAttachments(data);
            }
            setUploadingFiles(false);
          }

          toast({ title: "Voucher saved successfully!" });
          navigate(`/accounting/${journal_type}`);
        } else {
          setSaving(false);
          // Surface the actual server-side error message (covers 269ST / 40A(3) limit errors)
          const err = response.error;
          let description = "There was a problem with your request.";
          if (typeof err === "string") {
            description = err;
          } else if (Array.isArray(err)) {
            description = err.join(" ");
          } else if (err && typeof err === "object") {
            const msgs = Object.values(err).flat();
            description = msgs.join(" | ");
          }
          toast({
            title: "Voucher could not be saved",
            description,
            variant: "destructive",
          });
        }
      })
      .catch((error) => {
        setSaving(false);
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later.", variant: "destructive" });
      });
  };

  useF4Submit(handleSubmit(onSubmit));
  useF2Navigate(`/accounting/${journal_type}/add`);

  const handleEdit = (index) => {
    const row = rs[index];
    const value=getValues();
    reset({...value,table:row})
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
    markTableDirty();
  };

  // const fix_gold_rate = watch("fix_gold_rate")

  window.loadInvoices = (pmnts)=>{
    const status = getValues("table.status");
    const account = getValues("table.account");
    setValue("table.account", account);
    setValue("table.status", status);
    pmnts.forEach(pmnt => {
      const amt = parseFloat(pmnt.debit) || 0;
      setRows(prev => [...prev, {
        account: account,
        status: status,
        ref_bill_no: pmnt.bill_no,
        debit:  journal_type === "PMNT" ? amt : 0,
        credit: journal_type === "RECEIPT" ? amt : 0,
      }]);
    });
    markTableDirty();
  }

  const handleKeyDown = (e) => {

    if (e.key === "Tab") {
      const row = getValues("table");

      // ── If the user has picked bills in the BillAllocationTable, commit
      // the party row as multiple voucher_detail rows (one per allocated bill
      // + one "on account" row for any remainder). This is the multi-bill
      // payment path: e.g., 1,75,000 paid against bill-1 (1,50,000) and
      // bill-2 (25,000 of 50,000 outstanding).
      if ((journal_type === "PMNT" || journal_type === "RCPT") && allocations.length > 0) {
        const partyAmt = parseFloat(row.debit || 0) + parseFloat(row.credit || 0);
        const totalAlloc = allocations.reduce((s, a) => s + parseFloat(a.amount || 0), 0);

        if (totalAlloc > partyAmt + 0.01) {
          toast({
            title: "Allocation exceeds amount",
            description: `You've allocated ₹${totalAlloc.toLocaleString("en-IN")} across bills but the party row is only ₹${partyAmt.toLocaleString("en-IN")}.`,
            variant: "destructive",
          });
          e.preventDefault();
          return;
        }

        const isDebit = parseFloat(row.debit || 0) > 0;
        const expanded = allocations.map(a => ({
          account:    row.account,
          status:     "",
          ref_bill_no: a.billno,
          debit:      isDebit ? a.amount : 0,
          credit:     !isDebit ? a.amount : 0,
        }));

        // Remainder becomes an "on account" line with no ref_bill_no
        const remainder = partyAmt - totalAlloc;
        if (remainder > 0.01) {
          expanded.push({
            account:    row.account,
            status:     "",
            ref_bill_no: "",
            debit:      isDebit ? remainder : 0,
            credit:     !isDebit ? remainder : 0,
          });
        }

        setRows(prev => [...prev, ...expanded]);
        markTableDirty();
        setAllocations([]);
        setSelectedLedger(null);
        reset({ ...getValues(), table: { account: "", status: "", ref_bill_no: "", debit: "", credit: "" } });
        e.preventDefault();
        return;
      }

      // Validate: account must be filled, and at least one of debit/credit must be > 0
      const rowDebit = parseFloat(row.debit) || 0;
      const rowCredit = parseFloat(row.credit) || 0;
      if (!row.account || !row.account.trim()) {
        e.preventDefault();
        return;
      }
      if (rowDebit <= 0 && rowCredit <= 0) {
        toast({ title: "Enter a debit or credit amount", variant: "destructive" });
        e.preventDefault();
        return;
      }

      // Cash/Bank side restriction
      const ledger = selectedLedger;
      const isCashBank = ledger?.roles?.some(r => r.role === 'CA' || r.role === 'BA');
      if (isCashBank) {
        if (journal_type === 'RCPT' && rowCredit > 0) {
          toast({
            title: "Invalid entry",
            description: `${row.account} is a Cash/Bank account — it can only be debited in a Receipt voucher.`,
            variant: "destructive",
          });
          e.preventDefault();
          return;
        }
        if (journal_type === 'PMNT' && rowDebit > 0) {
          toast({
            title: "Invalid entry",
            description: `${row.account} is a Cash/Bank account — it can only be credited in a Payment voucher.`,
            variant: "destructive",
          });
          e.preventDefault();
          return;
        }
      }

      // Default: single-row add
      setRows(prev => [...prev, { ...row }])
      markTableDirty();
      setSelectedLedger(null);
      reset({...getValues(),
        table:{
          account:"",
          status:"",
          ref_bill_no:"",
          debit:"",
          credit:"",
        }
      }); e.preventDefault()
    }
  };

  const handleStatusKeyDown = (e) => {

    if (e.key === "Tab") {
      const status = getValues("table.status");
      const account = getValues("table.account");
      const customerId = selectedLedger?.id ?? null;
      console.log(status)
      if (status === "Against_Ref" &&  journal_type=== "PMNT"){
      const newWindow = window.open(`/accountadd/${journal_type}/${customerId}`, '_blank', 'width=800,height=600');

     }
     if (status === "Against_Ref" &&  journal_type=== "RECEIPT"){
      const newWindow = window.open(`/accountadd/${journal_type}/${customerId}`, '_blank', 'width=800,height=600');

     }


    }
  };



  if (!isValidType) return null;

  return (
    <div className="container mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        <h6 className="text-lg font-semibold">Add Journal Entry</h6>
        <hr className="my-3" />
        {preCustomerOrderId && (journal_type === "RCPT" || journal_type === "RCPT-SALE") && (
          <div className="my-3 flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3">
            <div className="flex-1 text-sm">
              <div className="font-semibold text-emerald-900">
                Advance receipt for order {preOrderNo || `#${preCustomerOrderId}`}
              </div>
              <div className="text-emerald-700 text-xs mt-0.5">
                This receipt will be linked to the customer order and automatically
                applied to the sales bill when the order is billed.
                {preLedgerName && <> Customer: <strong>{preLedgerName}</strong>.</>}
              </div>
            </div>
          </div>
        )}
        <br></br>
        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date")} required />
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="salesperson1" className="text-nowrap">Voucher Type</Label>
            <Controller
              name="form.voucher_type"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value} disabled readOnly>
                  <SelectTrigger >
                    <SelectValue placeholder="Select Voucher Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem key={"1"} value={`PMNT`}>Payment</SelectItem>
                    <SelectItem key={"2"} value={`CONTRA`}>Contra</SelectItem>
                    <SelectItem key={"3"} value={`RCPT`}>RECEIPT</SelectItem>
                    <SelectItem key={"8"} value={`JRNL`}>JOURNAL</SelectItem>

                  </SelectContent>
                </Select>
              )}
            />

          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="order_no" className="text-nowrap">Voucher No</Label>
            <Input type="text" {...register("form.voucher_no")} readOnly disabled />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Vendor Bill No</Label>
            <Input type="text" {...register("status")} />
          </FieldContainer>

        </div>

        <br></br>

        {(() => {
          const showStatus = journal_type !== "PMNT" && journal_type !== "RCPT";
          return (
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-14 px-4 py-2 border">Options</TableCell>
              <TableCell className="w-52 px-4 py-2 border">Account</TableCell>

              {showStatus && <TableCell className="w-28 px-4 py-2 border">Status</TableCell>}
              {showStatus && <TableCell className="w-28 px-4 py-2 border">Ref Bill No</TableCell>}
              <TableCell className="w-28 px-4 py-2 border">Debit</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Credit</TableCell>
            </TableRow>

            <TableRow>
              <TableCell className="w-14 px-4 py-2 border"></TableCell>
              <TableCell className="w-52 px-4 py-2 border">
                <SearchableComboBox
                  options={customers}
                  value={watch("table.account") ?? ""}
                  onInputChange={(val) => setValue("table.account", val)}
                  onSelect={(opt) => {
                    setValue("table.account", opt.ac_name);
                    setSelectedLedger(opt);
                  }}
                  placeholder="Search account..."
                />
              </TableCell>
              {showStatus && (
                <TableCell className="w-28 px-4 py-2 border">
                  <Input list="status_list" {...register("table.status")} onKeyDown={(e) => handleStatusKeyDown(e)} />
                  <datalist id="status_list">

                    <option key={1} value={"onAccount"}  > {"onAccount"}</option>
                    <option key={2} value={"Against_Ref"}  > {"Against_Ref"}</option>


                  </datalist>
                </TableCell>
              )}

              {showStatus && (
                <TableCell className="w-28 px-4 py-2 border">
                  <Input type="number" {...register("table.ref_bill_no")} />
                </TableCell>
              )}
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.debit")}/>
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.credit")} onKeyDown={(e) => handleKeyDown(e)} />
              </TableCell>



            </TableRow>
            {rs.map((row, index) => (
              <TableRow key={index} className="w-full bg-white">
                <TableCell className="w-14 px-4 py-2 border">
                  <div className="flex justify-center items-center gap-2">
                    <SquarePen
                      size={20}
                      className="cursor-pointer text-primary hover:text-primary"
                      onClick={() => handleEdit(index)}
                    />
                    <Trash2
                      size={20}
                      className="cursor-pointer text-red-600 hover:text-red-800"
                      onClick={() => handleDelete(index)}
                    />
                  </div>
                  {row.main_item}

                </TableCell>
                <TableCell className="w-52 px-4 py-2 border">{row.account}</TableCell>
                {showStatus && <TableCell className="w-16 px-4 py-2 border">{row.status}</TableCell>}
                {showStatus && <TableCell className="w-16 px-4 py-2 border">{row.ref_bill_no}</TableCell>}
                <TableCell className="w-24 px-4 py-2 border">{row.debit}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.credit}</TableCell>
              </TableRow>
            ))}

            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">{!showStatus ? "Total :" : ""}</TableCell>
              {showStatus && <TableCell className="w-32 px-4 py-2 border"></TableCell>}
              {showStatus && <TableCell className="w-32 px-4 py-2 border">Total : </TableCell>}
              <TableCell className="w-32 px-4 py-2 border">{totalDebit}</TableCell>
              <TableCell className="w-32 px-4 py-2 border">{totalCredit}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">{!showStatus ? "Difference :" : ""}</TableCell>
              {showStatus && <TableCell className="w-32 px-4 py-2 border"></TableCell>}
              {showStatus && <TableCell className="w-32 px-4 py-2 border">Difference : </TableCell>}
              <TableCell className="w-32 px-4 py-2 border">{totalCredit - totalDebit}</TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
            </TableRow>


          </TableBody>
        </Table>
          );
        })()}
        <br></br>

        {(journal_type === "PMNT" || journal_type === "RCPT") && (
          <div className="mt-3 mb-1 rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-xs text-blue-700 space-y-1">
            <p className="font-semibold">How to allocate against outstanding bills</p>
            <ol className="list-decimal list-inside space-y-0.5 text-blue-600">
              <li>Select the {journal_type === "PMNT" ? "vendor / supplier" : "customer"} account in the row above.</li>
              <li>Enter the total {journal_type === "PMNT" ? "payment" : "receipt"} amount in the {journal_type === "PMNT" ? "Debit" : "Credit"} field.</li>
              <li>In the table below, enter how much of that amount goes against each outstanding bill. Use <strong>Auto-fill (FIFO)</strong> to fill automatically.</li>
              <li>Press <kbd className="px-1 py-0.5 rounded bg-blue-100 font-mono">Tab</kbd> from the {journal_type === "PMNT" ? "Debit" : "Credit"} field to commit — one row per bill will be added to the voucher, with any remainder posted <em>on account</em>.</li>
            </ol>
          </div>
        )}

        {/* ── Bill-wise allocation picker (PMNT / RCPT only) ─────────────── */}
        {(journal_type === "PMNT" || journal_type === "RCPT") && (() => {
          const partyAmt    = parseFloat(watch("table.debit") || 0) + parseFloat(watch("table.credit") || 0);
          const currentLedger = selectedLedger;
          return (
            <BillAllocationTable
              ledgerId={currentLedger?.id}
              kind={journal_type === "PMNT" ? "purchase" : "sales"}
              partyAmount={partyAmt}
              allocations={allocations}
              onChange={setAllocations}
            />
          );
        })()}

        <br></br>

        <div className="grid grid-cols-1 gap-4 mb-4">

          <FieldContainer>
            <Label htmlFor="status" className="text-nowrap">Narration</Label>
            <Input
              type="text"
              {...register("form.narration")}
              onBlur={(e) => {
                const narration = e.target.value;
                const voucherType = watch("form.voucher_type") || "JRNL";
                if (narration?.trim().length >= 5) {
                  setNarrationForSuggestion({ narration, voucherType });
                }
              }}
            />
            <AccountSuggestion
              narration={narrationForSuggestion?.narration}
              voucherType={narrationForSuggestion?.voucherType}
              onApply={({ debitAccount, creditAccount }) => {
                // Insert or update the first two rows of the transactions table
                const tableRows = getValues("table.transactions") || [];
                if (tableRows.length > 0) {
                  setValue("table.transactions.0.account", debitAccount);
                } else {
                  // No rows yet — just store as a hint; user can add manually
                }
              }}
            />
          </FieldContainer>

        </div>

        {/* ── Attachments ── */}
        <div className="border rounded-lg p-4 mt-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Paperclip className="size-4 text-muted-foreground" />
            Attachments
            <span className="text-xs text-muted-foreground font-normal">
              ({(savedAttachments.length + pendingFiles.length)}/3)
            </span>
            {!savedVoucherId && pendingFiles.length > 0 && (
              <span className="text-xs text-amber-600 font-normal">— will upload when saved</span>
            )}
          </h3>

          {/* Saved attachments (edit mode or after save) */}
          {savedAttachments.map((att) => {
            const baseUrl = (sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/").replace(/\/$/, "");
            return (
              <div key={att.id} className="flex items-center gap-3 px-3 py-2 rounded-lg border bg-muted/20 mb-2">
                <FileText className="size-4 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <a
                    href={`${baseUrl}${att.file}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium hover:underline truncate block"
                  >
                    {att.original_name}
                  </a>
                  <span className="text-[10px] text-muted-foreground">
                    {new Date(att.uploaded_at).toLocaleDateString("en-GB")}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={async () => {
                    const res = await deleteVoucherAttachment(att.id);
                    if (res.success) setSavedAttachments((p) => p.filter((a) => a.id !== att.id));
                    else toast({ title: "Failed to remove attachment." });
                  }}
                  className="p-1 rounded hover:bg-destructive/10 text-destructive"
                  title="Remove"
                >
                  <X className="size-4" />
                </button>
              </div>
            );
          })}

          {/* Pending files (new voucher — queued for upload) */}
          {pendingFiles.map((file, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-dashed border-amber-300 bg-amber-50/40 mb-2">
              <FileText className="size-4 text-amber-600 shrink-0" />
              <span className="flex-1 text-sm truncate text-amber-800">{file.name}</span>
              <span className="text-[10px] text-amber-600 mr-2">pending</span>
              <button
                type="button"
                onClick={() => setPendingFiles((p) => p.filter((_, idx) => idx !== i))}
                className="p-1 rounded hover:bg-destructive/10 text-destructive"
                title="Remove"
              >
                <X className="size-4" />
              </button>
            </div>
          ))}

          {/* Upload control */}
          {(savedAttachments.length + pendingFiles.length) < 3 && (
            <label className="flex items-center gap-2 justify-center border-2 border-dashed border-border rounded-lg p-3 cursor-pointer hover:bg-muted/30 transition-colors mt-1">
              <Upload className="size-4 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                {uploadingFiles ? "Uploading…" : "Click to attach a file"}
              </span>
              <input
                type="file"
                className="hidden"
                disabled={uploadingFiles}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (savedVoucherId) {
                    // Voucher already exists — upload immediately
                    setUploadingFiles(true);
                    const res = await uploadVoucherAttachment(savedVoucherId, file);
                    if (res.success) {
                      const attRes = await getVoucherAttachments(savedVoucherId);
                      if (attRes.success) {
                        const data = Array.isArray(attRes.data) ? attRes.data : attRes.data?.results ?? [];
                        setSavedAttachments(data);
                      }
                      toast({ title: "File uploaded." });
                    } else {
                      const msg = typeof res.error === "string" ? res.error : res.error?.non_field_errors?.[0] || "Upload failed.";
                      toast({ title: msg, variant: "destructive" });
                    }
                    setUploadingFiles(false);
                  } else {
                    // New voucher — queue locally
                    setPendingFiles((p) => [...p, file]);
                  }
                  e.target.value = "";
                }}
              />
            </label>
          )}
        </div>

        {/* Submit */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>
            Cancel
          </Button>
          <Button type="submit" className="bg-primary hover:bg-primary text-white" disabled={saving || uploadingFiles || !canSave}>
            {uploadingFiles ? "Uploading files…" : saveLabel(saving)}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default AddJournal;



