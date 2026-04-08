
import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableBody } from "@/components/ui/table";
import {
  createHallmarkReceive,
  fetchPos,
  fetchHallmarkIssuewithslno,
  getLedgers,
  fetchNextHallMarkReceiveNo,
  fetchHallMarkRecForEdit,
  updateHallMarkRecForEdit,
} from "@/services/apiService";
import { useParams, useNavigate } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { renderErrorTree } from "@/Utils";

const HallmarkReceive = () => {
  const { toast } = useToast();
  const { id } = useParams();
  const navigate = useNavigate();

  const { register, handleSubmit, control, reset, watch, setValue, getValues } =
    useForm({
      defaultValues: {
        form: { date1: new Date().toISOString().split("T")[0] },
        table: [],
      },
    });

  const { fields, replace } = useFieldArray({
    control,
    name: "table",
  });

  const [customers, setCustomers] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [issueSlipSuggestions, setIssueSlipSuggestions] = useState([]);

  // 🔹 Fetch Issue Slip Data when user enters Issue Slip No
  const handleBlur = async () => {
    try {
      const { issue_slip_no } = getValues("form");
      if (!issue_slip_no) return;

      const data = await fetchHallmarkIssuewithslno(issue_slip_no);

      if (data.success && data.data.results.length > 0) {
        const result = data.data.results.find(
          (r) =>
            String(r.id) === String(issue_slip_no) ||
            String(r.issue_slip_no) === String(issue_slip_no)
        );

        if (!result) {
          toast({ title: "No matching Issue Slip found" });
          return;
        }

        const modifiedData = result.hallmarkissueitem_set.map((item) => ({
          ...item,
          issue_slip_no: result.id,
          hallmarkreceivedetails_set: item.hallmarkissuedetails_set, // rename for receive
        }));

        replace(modifiedData); // ✅ replace table with fetched rows
      } else {
        toast({ title: "No Issue Slip found for entered number" });
      }
    } catch (err) {
      console.error("Error fetching Issue Slip:", err);
      toast({ title: "Error fetching Issue Slip" });
    }
  };

  const slip_type = watch("slip_type");

  useEffect(() => {
    async function fetchData() {
      const [karigarsRes, hmbillno, customersRes, issuesRes] = await Promise.all([
        fetchPos(slip_type),
        fetchNextHallMarkReceiveNo(),
        getLedgers({type:"HM"}),
        fetchHallmarkIssuewithslno(), // fetch all issue slips for suggestions
      ]);

      if (karigarsRes.success) setKarigars(karigarsRes.data.results);
      if (hmbillno.success) setValue("form.receive_slip_no", hmbillno.data.bill_no);
      if (customersRes.success) setCustomers(customersRes.data.results);
      if (issuesRes.success) setIssueSlipSuggestions(issuesRes.data.results);
    }

    fetchData().then(() => {
      if (id) {
        fetchHallMarkRecForEdit(id).then((data) => {
          if (data.success) {
            const formData = {
              form: {
                ...data.data,
              },
              table: data.data.hallmarkreceiveitem_set || [],
            };

            // ✅ replace instead of append
            replace(formData.table);

            // ✅ set form fields
            Object.keys(formData.form).forEach((key) => {
              if (key !== "hallmarkreceiveitem_set") {
                setValue(`form.${key}`, formData.form[key]);
              }
            });
          }
        });
      }
    });
  }, [id, slip_type, replace, setValue]);

  const handleHallmarkReceiveSubmit = async () => {
    try {
      const data = getValues("form");
      const table_data = getValues("table");
      data.hallmarkreceiveitem_set = table_data;

      const response = await (id
        ? updateHallMarkRecForEdit(data, id)
        : createHallmarkReceive(data));

      if (response.success) {
        toast({ title: "Form submitted successfully!" });
        setTimeout(() => {
          navigate("/manufacturing/receive/hallmarkreceive/");
        }, 2000);
      } else {
        toast({
          title: "Form submission failed. Please try again.",
          description: renderErrorTree(response.error),
        });  // Error toast
      }
    } catch (error) {
      console.error("Error creating Hallmark Receive:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleHallmarkReceiveSubmit));

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(handleHallmarkReceiveSubmit)}
      >
        <hr className="my-3" />

        {/* Date, Issue Slip No, Receive Slip No */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="issue_slip_no" className="text-nowrap">
              Issue Slip No
            </Label>
            <Input
              type="text"
              {...register("form.issue_slip_no", { onBlur: handleBlur })}
              list="issue_list"
            />
            <datalist id="issue_list">
              {issueSlipSuggestions.map((issue, index) => (
                <option key={index} value={issue.issue_slip_no || issue.id} />
              ))}
            </datalist>
          </FieldContainer>

          <FieldContainer>
            <Label htmlFor="hallmark_center" className="text-nowrap">
              Receive Slip No
            </Label>
            <Input type="text" {...register("form.receive_slip_no")} />
          </FieldContainer>
        </div>

        {/* Hallmarking center */}
        <div className="grid grid-cols-3 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">
              Hallmarking center
            </Label>
            <Input
              list="party_list"
              {...register("form.hallmark_center_name")}
              onChange={(e) => {
                const selectedCustomer = customers.find(
                  (customer) => customer.ac_name === e.target.value
                );
                if (selectedCustomer) {
                  setValue("form.hallmark_center", selectedCustomer.id);
                }
              }}
              required
            />
            <Input type="hidden" {...register("form.hallmark_center")} />
            <datalist id="party_list">
              {customers.map((customer, index) => (
                <option key={index} value={customer.ac_name}>
                  {customer.id}
                </option>
              ))}
            </datalist>
          </FieldContainer>
        </div>

        {/* Items Table */}
        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className="w-full bg-gray-100">
              <TableCell className="w-16 px-4 py-2 border">S.No</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Gw</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Nw</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Loss wt</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Huid</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Rejection status</TableCell>
            </TableRow>

            {fields.map((field, index) => (
              <React.Fragment key={field.id}>
                <TableRow className="bg-violet-100">
                  <TableCell className="w-20 px-4 py-2 border">{field?.sl_no}</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">{field?.packet}</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">{field?.item}</TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{field?.purity}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">{field?.pcs}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">{field?.ct}</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">{field?.gw}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">{field?.nw}</TableCell>
                  <TableCell className="w-16 px-4 py-2 border">
                    <Input
                      type="text"
                      {...register(`table.${index}.loss_wt`)}
                      placeholder="loss weight"
                    />
                  </TableCell>
                  <TableCell className="w-16 px-4 py-2 border">
                    <Input
                      type="text"
                      {...register(`table.${index}.huid`)}
                      placeholder="huid"
                    />
                  </TableCell>
                  <TableCell className="w-16 px-4 py-2 border">
                    <Controller
                      name={`table.${index}.rejection_status`}
                      control={control}
                      render={({ field }) => (
                        <Checkbox
                          checked={!!field.value}
                          onCheckedChange={field.onChange}
                        />
                      )}
                    />
                  </TableCell>
                </TableRow>

                {field.hallmarkreceivedetails_set?.map((detail, detailIndex) => (
                  <TableRow key={detailIndex} className="bg-white">
                    <TableCell className="w-20 px-4 py-2 border">{detail?.sl_no}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.packet}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.item}</TableCell>
                    <TableCell className="w-24 px-4 py-2 border">{detail?.metal_purity}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">{detail?.pcs}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">{detail?.ct}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.gw}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">{detail?.nw}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border"></TableCell>
                    <TableCell className="w-32 px-4 py-2 border"></TableCell>
                    <TableCell className="w-32 px-4 py-2 border"></TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>

        {/* Submit */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>
            Cancel
          </Button>
          <Button type="submit" className="bg-primary hover:bg-primary text-white">
            Save
          </Button>
        </div>
      </form>
    </div>
  );
};

export default HallmarkReceive;