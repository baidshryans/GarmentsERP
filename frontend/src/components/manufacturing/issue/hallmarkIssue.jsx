import React, { useEffect, useState } from "react";
import { useForm, Controller, useFieldArray } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableBody } from "@/components/ui/table";
import { createHallmarkIssue, fetchPos, fetchMainItemDetails, fetchRCVs, fetchStoneIssuesFilterJobs, createKarigarIssue, fetchReceiveSlipNo } from "@/services/apiService";
import { Link, useParams } from "react-router-dom";
import { FieldContainer } from "@/Utils";
import { fetchHallmarkIssueForEdit, fetchNextHallMarkIssueNo, getLedgers, updateHallmarkIssue } from "../../../services/apiService";
import { useNavigate } from "react-router-dom";
import { renderErrorTree } from "../../../Utils";

const HallmarkIssue = () => {
  const { toast } = useToast()
  const { id } = useParams()
  const { register, handleSubmit, control, reset, watch, setValue, getValues } = useForm({
    defaultValues: {

      form: { date1: new Date().toISOString().split("T")[0], },

      table: []
    },
  });
  const { fields, append, remove } = useFieldArray({
    control,
    name: "table",
  });

  const navigate=useNavigate();
  const [rs, setRows] = useState([]);
  const [serialNos, setSerialNos] = useState([]);
  const [salespersonData, setSalespersonData] = useState([]);
  const [mainItemData, setMainItemData] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [purityData, setPurityData] = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [selected_recvitems,setSelectedRecvItems] = useState([])


  const handleBlur = async (e) => {

    const { receive_slip_no} = getValues('form');
    const karigar = karigars.find(k => k.receive_slip_no === receive_slip_no);
    setSelectedRecvItems([...karigar.karigarreceiveitem_set])
    console.log("Sett krrec ")


  }
  const handleBlur1 = async (e) => {

    const { receive_slip_no, sl_no } = getValues('form');
    console.log(receive_slip_no);
    console.log(sl_no);
    try {
      const karigar = karigars.find(k => k.receive_slip_no === receive_slip_no);
      console.log(karigar.karigarreceiveitem_set)
      console.log(sl_no)
      const item = karigar.karigarreceiveitem_set.find(i => i.sl_no === parseInt(sl_no));
      append(item);
    } catch (error) {
      console.error("Error fetching data:", error);
    }

  }



  useEffect(() => {
    async function fetchData() {
      const [karigars, customers, hmbillno] = await Promise.all([

        fetchRCVs(),
        // getLedgers(type='HM'),
        getLedgers({type:"HM"}),
        fetchNextHallMarkIssueNo()
      ]);

      if (karigars.success) setKarigars(karigars.data);
      if (customers.success) setCustomers(customers.data.results);
      if (hmbillno.success) setValue("form.issue_slip_no", hmbillno.data.bill_no);
    }
    fetchData().then(d => {
      if (id) {


        fetchHallmarkIssueForEdit(id)
          .then((response) => {

            // Set items array
            if (response.success) {
              const formData = {
                form: {
                  ...response.data,
                  hallmarkissueitem_set
                    : JSON.parse(JSON.stringify(response.data.
                      hallmarkissueitem_set

                    )),
                }
              };
              Object.keys(formData.form).forEach(key => {
                if (key === 'hallmarkissueitem_set') {
                  formData.form[key].forEach((item, index) => {
                    append(item);
                  });
                } else {
                  setValue(`form.${key}`, formData.form[key]);
                }
              });
            }
          })
          .catch((error) => {
            console.error('Error fetching manufacturing issue:', error);
          });
      }
    });
  }, []);
  const slip_type = watch("slip_type")
  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([
        fetchPos(slip_type),

      ]);
      if (karigars.success) setKarigars(karigars.data.results);
    }
    fetchData();
  }, [slip_type]);


  const handleHallmarkIssueSubmit = async () => {
    try {
      const data = getValues("form");
      const table_data = getValues("table");
      data.hallmarkissueitem_set = table_data;

      console.log(data);


      (!id ? createHallmarkIssue(data) : updateHallmarkIssue(id, data))
        .then((response) => {

          if (response.success) {
            toast({ title: "Form submitted successfully!" });

            setTimeout(() => {
              navigate("/manufacturing/issue/hallmarkissue/")
            }, 2000);

          } 
          else {
            toast({
              title: "Form submission failed. Please try again.",
              description: renderErrorTree(response.error),
            });  // Error toast
          }
        })
    } catch (error) {
      console.error("Error creating Sales Voucher:", error);
      toast({ title: "An error occurred. Please try again later." });
    }
  };

  useF4Submit(handleSubmit(handleHallmarkIssueSubmit));

  return (
    <div className="mt-5">
      <form
        className="p-4 shadow-lg rounded-lg bg-white"
        id="orderForm"
        onSubmit={handleSubmit(handleHallmarkIssueSubmit)}
      >

        <hr className="my-3" />

        {/* Date, Order No, Fixed Gold Rate */}
        <div className="grid grid-cols-4 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="date">Date</Label>
            <Input type="date" {...register("form.date1")} required />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="issue_slip_no" className="text-nowrap">Issue Slip No</Label>

            <Input type="text" {...register("form.issue_slip_no")} />

          </FieldContainer>







        </div>


        {/* Party Details */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <FieldContainer>
            <Label htmlFor="party_name_display" className="text-nowrap">Hallmarking center</Label>
            <Input list="party_list" {...register("form.hallmark_center_name",{
              onChange:(e) => {
                const selectedCustomer = customers.find(
                  (customer) => customer.ac_name === e.target.value
                );
                selectedCustomer ? setValue("form.hallmark_center", selectedCustomer.id) : e.target.value;

              }
            })}
               required />
                <datalist id="party_list" >
              {customers.map((customer, index) => (
                <option key={index} value={customer.ac_name}>{customer.id}</option>

              ))}

            </datalist>
            <Input type="hidden" {...register("form.hallmark_center")} />
           
          </FieldContainer>



        </div>



        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>

          </div>
          <FieldContainer>
            <Label htmlFor="receive_slip_no" className="text-nowrap">Receive Slip No</Label>
            <Input list="job_list"
              {...register("form.receive_slip_no",{ onBlur: (e) => handleBlur() })}

            />

            <datalist id="job_list" >
              {karigars.map((karigar, index) => (
                <option key={index} value={karigar.receive_slip_no}></option>

              ))}

            </datalist>

          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="sl_no" className="text-nowrap">Sl.No</Label>
            <Input
            list="job_sl_list"
              type="text"

              {...register("form.sl_no", { onBlur: (e) => handleBlur1() })}

            />
            <datalist id="job_sl_list" >
              {selected_recvitems
                .map((karigar, index) => (
                  <option key={index} value={karigar.sl_no}></option>

                ))}

            </datalist>
          </FieldContainer>


        </div>
        {/* <div className="grid grid-cols-3 gap-4 mb-4">
          <div></div>
          <FieldContainer>
            <Label htmlFor=" receive_slip_no " className="text-nowrap">Purchase Bill No</Label>
            <Input type="text" {...register("form.receive_sl ")} />
          </FieldContainer>
          <FieldContainer>
            <Label htmlFor="status">Sl.No</Label>
            <Input type="text" {...register("form.pur_sl_no ")} />
          </FieldContainer>
        </div> */}


        <Table className="w-full table-fixed border-collapse">
          <TableBody>
            <TableRow className=" w-full bg-gray-100">
              <TableCell className="w-16 px-4 py-2 border">S.No</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Packet</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Item</TableCell>
              <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>

              <TableCell className="w-16 px-4 py-2 border">Pcs</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Ct</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Gw</TableCell>
              <TableCell className="w-16 px-4 py-2 border">Nw</TableCell>
            </TableRow>
            {fields.map((field, index) => (
              <React.Fragment key={field.id}>
                <TableRow className="bg-violet-100">
                  <TableCell className="w-20 px-4 py-2 border">{field?.sl_no}</TableCell>
                  <TableCell className="w-16 px-4 py-2 border"></TableCell>
                  <TableCell className="w-16 px-4 py-2 border">{field?.item}</TableCell>
                  <TableCell className="w-24 px-4 py-2 border">{field?.purity}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">{field?.pcs}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border"></TableCell>
                  <TableCell className="w-16 px-4 py-2 border">{field?.gw}</TableCell>
                  <TableCell className="w-32 px-4 py-2 border">{field?.nw}</TableCell>
                </TableRow>
                {field.hallmarkissuedetails_set?.map((detail, detailIndex) => (
                  <TableRow key={detailIndex} className="bg-white">
                    <TableCell className="w-20 px-4 py-2 border">{detail?.sl_no}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.packet}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.item}</TableCell>
                    <TableCell className="w-24 px-4 py-2 border">{detail?.metal_purity}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">{detail?.pcs}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">{detail?.ct}</TableCell>
                    <TableCell className="w-16 px-4 py-2 border">{detail?.gw}</TableCell>
                    <TableCell className="w-32 px-4 py-2 border"></TableCell>
                  </TableRow>
                ))}
              </React.Fragment>
            ))}
          </TableBody>
        </Table>

        {/* Submit */}
        <div className="flex justify-end items-center gap-3 pt-4 border-t border-gray-100">
          <Button type="button" variant="outline" onClick={() => window.history.back()}>Cancel</Button>
          <Button type="submit" className="bg-violet-700 hover:bg-violet-800 text-white">
            Save
          </Button>
        </div>
      </form>
    </div>
  );
};

export default HallmarkIssue;

