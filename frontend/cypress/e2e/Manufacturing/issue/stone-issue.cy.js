/// working///

describe(' Add karigar issue Component', () => {
  it('should render the karigar issue form', () => {
    cy.visit("manufacturing/issue/stoneissue/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });


  cy.get('[data-id="slip-type"]').click();
  cy.get('[role="option"]').contains('Job Order').click();
  cy.wait(6000);
  

  cy.get('input[name="form.karigar_ldgr_name"]').type('A.Gupta');

  cy.get('input[list="job_list"]').type('IV/asfa/23232/00003');
  cy.wait(1500);

  cy.get('input[list="job_sl_list"]').focus();
  cy.wait(1500);
  
  cy.get('input[list="job_sl_list"]').type('1');

  cy.wait(3500);
  
  cy.get('input[name="table.packet"]').type('DR0005');
  cy.wait(1500);
  
  cy.get('input[name="table.pcs"]').type('2');

  cy.get('input[name="table.ct"]').type('2');
  cy.wait(1500);

  cy.get('input[name="table.gw"]').type('1');

  cy.get('input[name="table.remarks"]').type('gg');
  cy.get('input[name="table.remarks"]').realPress('Tab');
  
  cy.get('button[type="submit"]').click();

  cy.visit('manufacturing/issue/stoneissue/');



  });
});        
