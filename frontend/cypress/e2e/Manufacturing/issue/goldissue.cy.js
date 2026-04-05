/// working///


describe(' Gold issue Component', () => {
  it('should render the gold issue form', () => {
    cy.visit("/manufacturing/issue/goldissue/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

 
  cy.wait(3000);
  cy.get('[data-testid="slip-type"]').click();
  cy.get('[role="option"]').contains('Job Order').click()

  cy.get('input[name="form.karigar_ldgr_name"]').type('A.Gupta');
  
  cy.get('input[list="job_list"]').focus();
  cy.wait(1500);
  cy.get('input[list="job_list"]').type('IV/asfa/23232/00002');

  cy.get('input[list="job_sl_list"]').focus();
  cy.wait(1500);
  cy.get('input[list="job_sl_list"]').type('1');
  cy.get('input[list="job_sl_list"]').realPress('Tab');


 cy.get('input[name="table.item"]').type('GNS');

 cy.get('[data-testid="select-purity"]').click();
 cy.get('[role="option"]').contains('999').click();

 cy.get('input[name="table.item_gw"]').type('1');

 cy.get('[data-testid="purity"]').click();
 cy.get('[role="option"]').contains('24').click();
 cy.wait(1500);

 cy.get('input[name="table.remarks"]').type('gg');
 cy.get('input[name="table.remarks"]').realPress('Tab');

 cy.get('button[type="submit"]').click();
 cy.wait(3000);

 cy.visit('/manufacturing/issue/goldissue/');

  });
});            
