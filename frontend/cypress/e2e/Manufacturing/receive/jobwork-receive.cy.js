 /// karigar_ldgr are sometime time error///


describe('Jobwork Receive  Component', () => {
  it('should render the jobwork receive form', () => {
    cy.visit("manufacturing/receive/jobworkreceive/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

   cy.wait(1500);
   cy.get('input[name="form.karigar_ldgr_name"]').type('A.Gupta');
   cy.wait(2000);

   cy.get('input[name="form.ref_job_no"]').focus();
   cy.wait(1500);
   cy.get('input[name="form.ref_job_no"]').type('IV/asfa/23232/00002');
   cy.wait(1000);
   cy.get('input[name="form.sl_no"]').focus();

   cy.get('input[name="form.sl_no"]').type('1');
   cy.get('input[name="form.sl_no"]').realPress('Tab');

  
   cy.get('input[name="table.0.making"]').type('5');

   cy.get('input[name="table.0.rhodium"]').type('7');
   cy.wait(1500);

  
// /// goods issued///
//  cy.get('input[name="table.0.details.0.issue_gw"]').type('0.4');
//  cy.wait(1500);
//  cy.get('input[name="table.0.details.0.broken_gw"]').type('5');

// /// item used in jewelery///

// cy.get('input[name="table.0.details.0.balance_gw"]').type('1');


// cy.get('input[name="advance_amt"]').type('2');

cy.get('input[name="sgst_per"]').type('0.01');

cy.get('input[name="cgst_per"]').type('0.01');

cy.get('input[name="igst_per"]').type('0.01');
// cy.wait(1500);


cy.get('button[type="submit"]').click();

// cy.visit('manufacturing/receive/jobworkreceive/');

});
});  