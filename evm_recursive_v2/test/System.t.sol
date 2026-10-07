// SPDX-License-Identifier: MIT
pragma solidity 0.8.37;
import "../src/TestToken.sol";
import "../src/CPMMPool.sol";
import "../src/RiskOracle.sol";
import "../src/Treasury.sol";
import "../src/CollateralVault.sol";
import "../src/RecursiveEngine.sol";

contract SystemTest {
    uint256 constant W=1e18;
    TestToken x;TestToken z;TestToken u;TestToken c;RiskOracle oracle;Treasury treasury;CollateralVault vault;RecursiveEngine engine;
    CPMMPool xu;CPMMPool zu;CPMMPool xz;CPMMPool xc;CPMMPool zc;

    function setUp() public {
        x=new TestToken("RUBX","RUBX",18);z=new TestToken("RUBZ","RUBZ",18);u=new TestToken("USDC","USDC",18);c=new TestToken("COLL","COLL",18);
        oracle=new RiskOracle();treasury=new Treasury();vault=new CollateralVault(address(oracle),address(treasury));
        xu=new CPMMPool(address(x),address(u),30,"XU","XU");zu=new CPMMPool(address(z),address(u),30,"ZU","ZU");xz=new CPMMPool(address(x),address(z),30,"XZ","XZ");xc=new CPMMPool(address(x),address(c),30,"XC","XC");zc=new CPMMPool(address(z),address(c),30,"ZC","ZC");
        engine=new RecursiveEngine(address(x),address(z),address(u),address(c),address(treasury),address(vault),address(xu),address(zu),address(xz),address(xc),address(zc));
        x.setMinter(address(engine),true);z.setMinter(address(engine),true);treasury.setOperator(address(engine),true);treasury.setOperator(address(vault),true);vault.setOperator(address(engine));
        vault.setHardToken(address(u),true);vault.setHardToken(address(c),true);oracle.setPrice(address(x),W);oracle.setPrice(address(z),W);oracle.setPrice(address(u),W);oracle.setPrice(address(c),W);
        vault.configurePool(address(xu),6500);vault.configurePool(address(zu),6500);vault.configurePool(address(xz),0);vault.configurePool(address(xc),6500);vault.configurePool(address(zc),6500);vault.setRisk(5000,2500,12500);
        u.mint(address(this),10*W);c.mint(address(this),10*W);x.mint(address(this),10*W);z.mint(address(this),10*W);
        _seed(xu,.0625 ether,.0625 ether);_seed(zu,.0625 ether,.0625 ether);_seed(xc,.0625 ether,.0625 ether);_seed(zc,.0625 ether,.0625 ether);_seed(xz,1 ether,1 ether);u.transfer(address(treasury),.25 ether);
    }

    function testInitialHardNavIsHalfDollar() public {require(engine.hardNav()==.5 ether,"HNAV0");}
    function testMintSellNoFreeHardNav() public {uint256 b=engine.hardNav();engine.mintSellX(.005 ether);require(engine.hardNav()==b,"NO_FREE_HNAV");}
    function testExternalRevenueAddsHardNav() public {uint256 b=engine.hardNav();u.approve(address(treasury),1 ether);treasury.depositExternalRevenue(address(u),1 ether);require(engine.hardNav()==b+1 ether,"EXT");}
    function testDividendNeedsRevenue() public {(bool ok,)=address(treasury).call(abi.encodeWithSelector(treasury.payDividend.selector,address(u),address(this),.02 ether));require(!ok,"DIV");}
    function _seed(CPMMPool p,uint256 a0,uint256 a1) internal {TestToken(p.token0()).approve(address(p),a0);TestToken(p.token1()).approve(address(p),a1);p.addLiquidity(a0,a1,address(this));}
}
