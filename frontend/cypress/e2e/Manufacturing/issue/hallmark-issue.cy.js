/// ldgr some time error occur///
describe(' Hallmark issue Component', () => {
  it('should render the hallmark issue form', () => {
    cy.visit("manufacturing/issue/hallmarkissue/add/",{
      onBeforeLoad(win) {
        window.localStorage.setItem('Token', '76fb2f9b9e0eb3806b6e3289c178927ee3403c8b'); 
        window.localStorage.setItem('retail_code', 'asfa'); 
      },
    });

  cy.wait(2000);
  cy.get('input[name="form.hallmark_center_name"]').type('A.Gupta');
  cy.wait(1000);

  cy.get('input[name="form.receive_slip_no"]').focus();
  cy.wait(2000);
  cy.get('input[name="form.receive_slip_no"]').type('RS/asfa/23232/00001');

  cy.get('input[name="form.sl_no"]').focus();
  cy.wait(1500);
  cy.get('input[name="form.sl_no"]').type('1');
  cy.get('input[name="form.sl_no"]').realPress('Tab');
  cy.wait(1500);
  cy.get('button[type="submit"]').click();





  });
});        