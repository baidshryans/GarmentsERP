///  working  ///

describe('Stone Return Component', () => {
  it('should render the stone return form', () => {
    cy.visit("manufacturing/receive/stonereturn/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });


  cy.get('[data-id="slip-type"]').click();
  cy.get('[role="option"]').contains('Job Order').click();
  cy.wait(5000);

  cy.get('input[name="form.karigar_ldgr_name"]').type('A.Gupta');
  
  cy.get('input[list="job_list"]').focus();
  cy.wait(1500);
  cy.get('input[list="job_list"]').type('IV/asfa/23232/00002');

  cy.get('input[list="job_sl_list"]').focus();
  cy.wait(1500);
  cy.get('input[list="job_sl_list"]').type('1');
  cy.get('input[list="job_sl_list"]').realPress('Tab');

   

/// goods returned back///
  cy.wait(2500);
  cy.get('input[name="table.packet"]').type('DR0003');

  cy.get('input[name="table.return_pcs"]').type('2');

  cy.get('input[name="table.return_ct"]').type('1');

  cy.get('input[name="table.sgst"]').type('2');

  cy.get('input[name="table.igst"]').type('3');

  cy.get('input[name="table.tot_val"]').type('10');

  cy.get('input[name="remarks"]').type('ok');
  cy.get('input[name="remarks"]').realPress('Tab');

  // cy.get('input[name="advance_amt"]').type('2');
  cy.get('input[name="form.sgst_per"]').type('0.01');
  cy.get('input[name="form.cgst_per"]').type('0.02');
  cy.get('input[name="form.igst_per"]').type('0.01');
  cy.get('input[name="advances_amt"]').type('100');

  cy.get('button[type="submit"]').click();
  cy.wait(1500);

  cy.visit('manufacturing/receive/stonereturn/');




});
});      