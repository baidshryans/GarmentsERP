


describe('SalesApproval Component', () => {
  it('should render the sales Approval form', () => {
    cy.visit('sales/salesapproval/list/add/', {
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b');
        window.localStorage.setItem('retail_code', 'asfa');
      },
    });


   cy.wait(5000);
   cy.get('input[name="form.gst_billno"]').type('67857');

   cy.get('input[name="form.ldgr_name"]').type('A K Jain');

   cy.get('[data-id="sp-1"]').click();
   cy.wait(1000);
   cy.get('[role="option"]').contains('John Doe').click();

   cy.get('[data-id="sp-2"]').click();
   cy.get('[role="option"]').contains('Emily Davis').click();

  //  cy.get('[data-id="place"]').click();
  //  cy.get('[role="option"]').contains('Odisha').click();

   cy.get('input[name="form.remarks"]').type('gg');

   cy.get('input[name="form.mrp"]').type('100');

  //  cy.get('[ data-id="gst-type"]').click();
  //  cy.get('[role="option"]').contains('LOCAL').click();

   cy.get('input[name="form.mode_of_transport"]').type('aded');

   cy.get('[data-id="hsn-code"]').click();
   cy.get('[role="option"]').contains('711319').click();

   cy.get('input[name="barcode"]').type('9719135787656');

   cy.get('input[name="barcode"]').realPress('Tab');

   cy.wait(2500);
   
  //  cy.get('input[name="salesvouitem_set.0.making"]').type('654');

  cy.get('input[name="salevouitem_set.0.amount"]').type('2000');
  cy.wait(3000);
  cy.get('inpu[name="salesvouitem_set.0.main_item_set.0.tunch"]').type('0.1');

  cy.get('input[name="slaesvouitem_set.0.main_item_set.0.amount"]').type('500');

  cy.get('input[name="form.narration"]').type('dfe');

  cy.get('input[name="form.taxable_value"]').type('1');

  cy.get('input[name="form.discount"]').type('0.2');

  cy.get('input[name="form.cgst_per"]').type('0.2');

  cy.get('input[name="form.sgst_per"]').type('0.1');

  cy.get('input[name="form.tcs_per"]').type('0.2');

  cy.get('input[name="form.tcs_amt"]').type('0.2');

  cy.get('button[type="submit"]').click();



  });
});    