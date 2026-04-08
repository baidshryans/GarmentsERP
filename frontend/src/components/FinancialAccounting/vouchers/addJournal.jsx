import React, { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { fetchMainItem, fetchOrderNoNext, fetchSalesperson, fetchPurity, getLedgers, createCustomerOrder, createJournalEntry, getVoucherAttachments, uploadVoucherAttachment, deleteVoucherAttachment } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchAccountingVoucher, fetchJournalEntryForEdit, fetchVoucherNoNext, updateJournalEntryForEdit } from "../../../services/apiService";
import { Edit, Trash2, Paperclip, Upload, FileText, X } from "lucide-react";
import AccountSuggestion from "@/components/AI/AccountSuggestion";

const AddJournal = () => {
  const { toast } = useToast()
  const {id} = useParams()
  const { journal_type } = useParams();
  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {

      form: {
        date: new Date().toISOString().split("T")[0],

        voucher_type: ""
      },
      table: { credit: 0, debit: 0 }

    },
  });
  const [rs, setRows] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [narrationForSuggestion, setNarrationForSuggestion] = useState(null);
  const [savedVoucherId, setSavedVoucherId] = useState(id || null);
  const [savedAttachments, setSavedAttachments] = useState([]);   // already uploaded (edit mode)
  const [pendingFiles, setPendingFiles]         = useState([]);   // queued (add mode, uploaded on save)
  const [uploadingFiles, setUploadingFiles]     = useState(false);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [totalCredit, settotalCredit] = useState(0);
  const [totalDebit, settotalDebit] = useState(0);

  // Load existing attachments when editing
  useEffect(() => {
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
      })
      .catch((error) => {
        console.error('Error fetching manufacturing issue:', error);
      });
    

  }, [journal_type, setValue]);

  useEffect(() => {
    const totalDebit = rs.reduce((acc, row) => acc + parseFloat(row.debit), 0);
    const totalCredit = rs.reduce((acc, row) => acc + parseFloat(row.credit), 0);
    settotalDebit(totalDebit);
    settotalCredit(totalCredit);

  }, [rs]);

  useEffect(() => {
    async function fetchData() {
      const [customers, salesperson, orderNo, mainItem, purity] = await Promise.all([
        getLedgers({type:""}),
        fetchSalesperson(),
        fetchVoucherNoNext(journal_type),
        fetchMainItem(),
        fetchPurity(),
      ]);
      if (customers.success) setCustomers(customers.data.results);
      if (salesperson.success) setSalespersonData(salesperson.data.results);
      if (!id && orderNo.success) setValue("form.voucher_no", orderNo.data.billno);
      if (mainItem.success) setMainItemData(mainItem.data.results);
      if (purity.success) setPurityData(purity.data.results);
    }
    fetchData();
  }, []);

  const account_name = watch('table.account')

  useEffect(()=>{
    getLedgers({search:account_name,type:""}).then(customers => {
      if (customers.success) setCustomers(customers.data.results);
    })
  },[account_name])

  const onSubmit = (data) => {
    const form = getValues('form')
    form.voucher_details = [...rs];

    console.log(form)
    if (totalCredit - totalDebit !== 0) {
      toast({ title: "Debit and Credit should be equal" });
      return;
    }

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
        } else {
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
        console.error("Error submitting form:", error);
        toast({ title: "An error occurred. Please try again later.", variant: "destructive" });
      });
  };

  useF4Submit(handleSubmit(onSubmit));

  const handleEdit = (index) => {
    const row = rs[index];
    const value=getValues();
    reset({...value,table:row})
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleDelete = (index) => {
    setRows((prev) => prev.filter((_, i) => i !== index));
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
  }

  const handleKeyDown = (e) => {

    if (e.key === "Tab") {
      const row = getValues("table");
      console.log(row)
      console.log(rs)
      
      setRows(prev => [...prev, { ...row }])
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
      const customer = customers.find(c => c.ac_name === account);
      const customerId = customer ? customer.id : null;
      console.log(status)
      if (status === "Against_Ref" &&  journal_type=== "PMNT"){
      const newWindow = window.open(`/accountadd/${journal_type}/${customerId}`, '_blank', 'width=800,height=600');

     }
     if (status === "Against_Ref" &&  journal_type=== "RECEIPT"){
      const newWindow = window.open(`/accountadd/${journal_type}/${customerId}`, '_blank', 'width=800,height=600');

     }


    }
  };



  return (
    <div className="container mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(onSubmit)}
      >
        <h6 className="text-lg font-semibold">Add Journal Entry</h6>
        <hr className="my-3" />
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

        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-28 px-4 py-2 border">Options</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Account</TableCell>

              <TableCell className="w-28 px-4 py-2 border">Status</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Ref Bill No</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Debit</TableCell>
              <TableCell className="w-28 px-4 py-2 border">Credit</TableCell>
            </TableRow>

            <TableRow>
              <TableCell className="w-28 px-4 py-2 border"></TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input list="item_list" {...register("table.account")} />
                <datalist id="item_list">
                  {customers.map((item, index) => (
                    <option key={index} value={item.ac_name}  > {item.ac_name}</option>
                  ))}

                </datalist>
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input list="status_list" {...register("table.status")} onKeyDown={(e) => handleStatusKeyDown(e)} />
                <datalist id="status_list">

                  <option key={1} value={"onAccount"}  > {"onAccount"}</option>
                  <option key={2} value={"Against_Ref"}  > {"Against_Ref"}</option>


                </datalist>
              </TableCell>

              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.ref_bill_no")} />
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.debit")}/>
              </TableCell>
              <TableCell className="w-28 px-4 py-2 border">
                <Input type="number" {...register("table.credit")} onKeyDown={(e) => handleKeyDown(e)} />
              </TableCell>



            </TableRow>
            {rs.map((row, index) => (
              <TableRow key={index} className="w-full bg-white">
                <TableCell className="w-28 px-4 py-2 border">
                  <div className="flex justify-center items-center gap-2">
                    <Edit
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
                <TableCell className="w-20 px-4 py-2 border">{row.account}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.status}</TableCell>
                <TableCell className="w-16 px-4 py-2 border">{row.ref_bill_no}</TableCell>
                <TableCell className="w-24 px-4 py-2 border">{row.debit}</TableCell>
                <TableCell className="w-32 px-4 py-2 border">{row.credit}</TableCell>
              </TableRow>
            ))}

            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">Total : </TableCell>
              <TableCell className="w-32 px-4 py-2 border">{totalDebit}</TableCell>

              <TableCell className="w-32 px-4 py-2 border">{totalCredit}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>
              <TableCell className="w-32 px-4 py-2 border">Difference : </TableCell>
              <TableCell className="w-32 px-4 py-2 border">{totalCredit - totalDebit}</TableCell>
              <TableCell className="w-32 px-4 py-2 border"></TableCell>

            </TableRow>


          </TableBody>
        </Table>
        <br></br> <br></br>

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
            <Paperclip className="w-4 h-4 text-muted-foreground" />
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
                <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
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
                  <X className="w-4 h-4" />
                </button>
              </div>
            );
          })}

          {/* Pending files (new voucher — queued for upload) */}
          {pendingFiles.map((file, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg border border-dashed border-amber-300 bg-amber-50/40 mb-2">
              <FileText className="w-4 h-4 text-amber-600 shrink-0" />
              <span className="flex-1 text-sm truncate text-amber-800">{file.name}</span>
              <span className="text-[10px] text-amber-600 mr-2">pending</span>
              <button
                type="button"
                onClick={() => setPendingFiles((p) => p.filter((_, idx) => idx !== i))}
                className="p-1 rounded hover:bg-destructive/10 text-destructive"
                title="Remove"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}

          {/* Upload control */}
          {(savedAttachments.length + pendingFiles.length) < 3 && (
            <label className="flex items-center gap-2 justify-center border-2 border-dashed border-border rounded-lg p-3 cursor-pointer hover:bg-muted/30 transition-colors mt-1">
              <Upload className="w-4 h-4 text-muted-foreground" />
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
          <Button type="submit" className="bg-primary hover:bg-primary text-white" disabled={uploadingFiles}>
            {uploadingFiles ? "Uploading files…" : "Save"}
          </Button>
        </div>
      </form>
    </div>
  );
};

export default AddJournal;
