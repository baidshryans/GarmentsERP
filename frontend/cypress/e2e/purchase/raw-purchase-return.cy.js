describe('Raw Purchase return Component', () => {
  it('should render the rawpurchase return form', () => {
    cy.visit('/purchase/rawpurchasereturn/add/',{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

 cy.wait(2500);
 cy.get('input[name="form.mode_of_transport"]').type('dwf');
 cy.wait(1500);
 cy.get('input[name="form.pv_billno"]').type('	PV/asfa/23232/00012');
 cy.get('input[name="form.pv_billno"]').realPress('Tab');
 cy.wait(1000);

 cy.get('input[name="form.narration"]').type('fwfw');

 cy.get('input[name="form.item_total"]').type('5');

 cy.get('input[name="form.tcs_amt"]').type('2');

 cy.get('input[name="form.taxable_value"]').type('.01');

 cy.get('input[name="form.discount"]').type('.01');

 cy.get('input[name="form.cgst_amt"]').type('.03');

 cy.get('input[name="form.sgst_amt"]').type('.04');

 cy.get('input[name="form.igst_amt"]').type('.01');

// cy.get('button[type="submit"]').click();
// cy.wait(2000);



 });
});