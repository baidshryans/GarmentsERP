/// working///
describe('Hallmark Receive  Component', () => {
  it('should render the hallmark receive form', () => {
    cy.visit("manufacturing/receive/hallmarkreceive/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

 
 
 cy.get('input[name="form.issue_slip_no"]').focus();
 cy.wait(1500);
 cy.get('input[name="form.issue_slip_no"]').type('HMIS/asfa/23232/00001');

 cy.get('input[name="form.hallmark_center_name"]').type('A.Gupta',{force:true});
 cy.wait(2500);
 
 cy.get('input[name="table.0.loss_wt"]').type('0.1')

 cy.get('input[name="table.0.huid"]').type('2')

 
 cy.get('[role="checkbox"]').click()
 .should('have.attr','aria-checked','true');

 cy.get('button[type="submit"]').click();
 cy.wait(1000);

 cy.visit('/manufacturing/receive/hallmarkreceive/');

});
});      